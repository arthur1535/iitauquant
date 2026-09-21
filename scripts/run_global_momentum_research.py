"""Pesquisa quantitativa e backtest para ativos globais líderes de momentum."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.engine import ExecutionConfig, run_backtest
from strategies.momentum_atr import MomentumATRConfig, validate_ohlc

DATA_DIR = ROOT / "data" / "market"
OUTPUT_DIR = ROOT / "results" / "global_research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GLOBAL_TICKERS = [
    "NVDA",
    "MSFT",
    "AAPL",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "QQQ",
    "SPY",
    "SMH",
    "GLD",
]


def run_global_research() -> pd.DataFrame:
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    records = []
    for ticker in GLOBAL_TICKERS:
        parquet_path = DATA_DIR / f"{ticker}.parquet"
        if not parquet_path.exists():
            print(f"Aviso: {parquet_path} não encontrado.")
            continue

        raw = pd.read_parquet(parquet_path)
        clean = validate_ohlc(raw)
        res = run_backtest(clean, strategy, execution)

        m = res.metrics
        records.append({
            "ticker": ticker,
            "bars": m["bars"],
            "trades": m["total_trades"],
            "win_rate_pct": round(m["win_rate"] * 100, 2),
            "total_return_pct": round(m["total_return"] * 100, 2),
            "annualized_return_pct": round(m["annualized_return"] * 100, 2),
            "annualized_vol_pct": round(m["annualized_volatility"] * 100, 2),
            "sharpe_ratio": round(m["sharpe_ratio"], 3),
            "max_drawdown_pct": round(m["max_drawdown"] * 100, 2),
            "profit_factor": round(m["profit_factor"], 2),
        })

        # Gravar curvas de equity e trades individuais
        res.equity_curve.to_csv(OUTPUT_DIR / f"{ticker}_equity.csv")
        res.trades.to_csv(OUTPUT_DIR / f"{ticker}_trades.csv", index=False)

    df = pd.DataFrame(records).sort_values(by="sharpe_ratio", ascending=False).reset_index(drop=True)
    df.to_csv(OUTPUT_DIR / "global_leaders_metrics.csv", index=False)
    
    # Gerar relatório comparativo em Markdown
    md_content = "# Desempenho Quantitativo: Cesta de Ativos Globais de Alta Qualidade (2020 - 2026)\n\n"
    md_content += "Simulação causal (decisão no fechamento $t$, execução no open $t+1$), com custos bilaterais de 15 bps e trailing stop ATR Ratchet:\n\n"
    headers = list(df.columns)
    md_table = "| " + " | ".join(headers) + " |\n"
    md_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for _, row in df.iterrows():
        md_table += "| " + " | ".join(str(row[h]) for h in headers) + " |\n"
    md_content += md_table
    md_content += "\n\n"
    (OUTPUT_DIR / "global_leaders_report.md").write_text(md_content, encoding="utf-8")
    
    print("\n--- RESULTADOS GLOBAIS (RANKING POR SHARPE) ---")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    run_global_research()
