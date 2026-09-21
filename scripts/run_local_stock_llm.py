"""Run a local, paper-only equity analysis with a quantized LLM on CUDA.

The model receives a deterministic price/technical snapshot and optional local
research text. It is explicitly prompted not to invent fundamentals, prices,
targets, or trading instructions. This is a research aid; it does not place
orders and does not replace the repository's backtests or OOS gates.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_REPORT = Path("results/china_research/relatorio_pesquisa_china.md")


def _require_runtime() -> tuple[Any, Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:  # pragma: no cover - depends on optional local extra
        raise SystemExit(
            "Dependências ausentes. Execute scripts\\setup_local_llm.ps1 primeiro."
        ) from exc

    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA não está disponível neste Python. Execute o setup_local_llm.ps1 "
            "e confirme que o driver NVIDIA está instalado."
        )
    return torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def _rsi(close: pd.Series, window: int = 14) -> float | None:
    delta = close.diff()
    gains = delta.clip(lower=0).rolling(window).mean()
    losses = (-delta.clip(upper=0)).rolling(window).mean()
    if losses.empty or pd.isna(losses.iloc[-1]) or losses.iloc[-1] == 0:
        return 100.0 if not gains.empty and gains.iloc[-1] > 0 else None
    return float(100 - 100 / (1 + gains.iloc[-1] / losses.iloc[-1]))


def _max_drawdown(close: pd.Series) -> float | None:
    if close.empty:
        return None
    wealth = close / close.iloc[0]
    drawdown = wealth / wealth.cummax() - 1
    return float(drawdown.min() * 100)


def _period_return(close: pd.Series, periods: int) -> float | None:
    if len(close) <= periods:
        return None
    return float((close.iloc[-1] / close.iloc[-periods - 1] - 1) * 100)


def fetch_snapshot(ticker: str, period: str) -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("yfinance ausente; execute o setup_local_llm.ps1.") from exc

    data = yf.download(ticker, period=period, interval="1d", auto_adjust=True, progress=False)
    if data.empty:
        raise SystemExit(f"Nenhuma série OHLC foi retornada para {ticker}.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(data.columns)
    if missing:
        raise SystemExit(f"Série de {ticker} sem colunas: {sorted(missing)}")

    close = pd.to_numeric(data["Close"], errors="coerce").dropna()
    high = pd.to_numeric(data["High"], errors="coerce")
    low = pd.to_numeric(data["Low"], errors="coerce")
    if len(close) < 220:
        raise SystemExit(f"A série de {ticker} tem apenas {len(close)} barras; mínimo recomendado: 220.")

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]
    ret = close.pct_change().dropna()
    latest = float(close.iloc[-1])
    snapshot = {
        "ticker": ticker.upper(),
        "period": period,
        "bars": int(len(close)),
        "last_date": str(close.index[-1].date()),
        "last_close_adjusted": round(latest, 4),
        "return_1m_pct": _period_return(close, 21),
        "return_3m_pct": _period_return(close, 63),
        "return_1y_pct": _period_return(close, 252),
        "return_full_period_pct": round(float((latest / close.iloc[0] - 1) * 100), 2),
        "sma20": round(float(close.rolling(20).mean().iloc[-1]), 4),
        "sma50": round(float(close.rolling(50).mean().iloc[-1]), 4),
        "sma200": round(float(close.rolling(200).mean().iloc[-1]), 4),
        "rsi14": round(_rsi(close) or math.nan, 2),
        "atr14_pct_of_price": round(float(atr14 / latest * 100), 2),
        "annualized_volatility_pct": round(float(ret.std() * (252**0.5) * 100), 2),
        "max_drawdown_pct": round(_max_drawdown(close) or math.nan, 2),
        "above_sma50": bool(latest > close.rolling(50).mean().iloc[-1]),
        "above_sma200": bool(latest > close.rolling(200).mean().iloc[-1]),
    }
    return snapshot


def read_report(path: Path | None, max_chars: int) -> str:
    if path is None or not path.exists():
        return "Nenhum relatório local adicional foi fornecido."
    text = path.read_text(encoding="utf-8")
    return text[:max_chars]


def build_prompt(snapshot: dict[str, Any], report: str) -> list[dict[str, str]]:
    data = json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False)
    system = (
        "Você é um analista quantitativo auxiliar em modo paper-only. "
        "Use somente os dados fornecidos. Não invente preço atual, fundamentos, "
        "notícias, valuation, consenso ou alvo. Separe fatos, inferências e dados "
        "ausentes. Nunca mencione um período de retorno que não esteja no JSON. "
        "RSI é um oscilador e não mede volatilidade; use ATR, volatilidade anualizada "
        "e drawdown para risco. Não dê ordem de compra/venda. Responda em português claro."
    )
    user = f"""Faça uma triagem disciplinada para {snapshot['ticker']}.

Dados técnicos calculados pelo pipeline:
```json
{data}
```

Relatório local opcional (pode não mencionar este ticker):
```text
{report}
```

Entregue exatamente estas seções:
1. Leitura do regime (tendência, momentum e volatilidade).
2. O que os dados sustentam e o que eles não sustentam.
3. Riscos que precisam de diligência fundamentalista (receita, margem, fluxo de caixa,
   dívida, governança, liquidez, ADR/VIE e risco regulatório quando aplicável).
4. Próximo teste reproduzível no repositório (OOS, drawdown, custos e benchmark).
5. Veredito: `passa para pesquisa`, `somente satélite especulativo` ou `insuficiente`.
Não transforme o veredito em recomendação personalizada."""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_model(model_id: str, messages: list[dict[str, str]], max_new_tokens: int) -> tuple[str, float, str]:
    torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig = _require_runtime()
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant,
        device_map="auto",
        dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
    input_device = model.get_input_embeddings().weight.device
    inputs = {key: value.to(input_device) for key, value in inputs.items()}
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        model.generation_config.temperature = None
        model.generation_config.top_p = None
        model.generation_config.top_k = None
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = output[0, inputs["input_ids"].shape[1] :]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
    peak_gib = torch.cuda.max_memory_allocated() / 2**30
    gpu = torch.cuda.get_device_name(0)
    return answer, peak_gib, gpu


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True, help="Ticker aceito pelo Yahoo Finance, por exemplo NVDA ou VALE3.SA")
    parser.add_argument("--period", default="2y", help="Período aceito pelo yfinance; padrão: 2y")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo Hugging Face; padrão: {DEFAULT_MODEL}")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Relatório local opcional")
    parser.add_argument("--max-report-chars", type=int, default=8000)
    parser.add_argument("--max-new-tokens", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = fetch_snapshot(args.ticker, args.period)
    messages = build_prompt(snapshot, read_report(args.report, args.max_report_chars))
    answer, peak_gib, gpu = run_model(args.model, messages, args.max_new_tokens)
    print(f"GPU: {gpu} | pico VRAM: {peak_gib:.2f} GiB")
    print(f"Modelo: {args.model}")
    print(f"Snapshot: {snapshot['ticker']} em {snapshot['last_date']} ({snapshot['bars']} barras)")
    print("\n" + "=" * 80 + "\n")
    print(answer)


if __name__ == "__main__":
    main()
