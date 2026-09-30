"""Análise quantitativa da cadeia do urânio: SPUT (U.UN/SRUUF), Centrus (LEU),
Paladin (PDN/PALAF) e Cameco (CCJ), com URA e SPY como referências."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backtest.engine import ExecutionConfig, calculate_performance_metrics, run_backtest
from backtest.statistics import deflated_sharpe_probability, expected_maximum_sharpe
from backtest.stress import run_stress_matrix
from strategies.momentum_atr import MomentumATRConfig, validate_ohlc

DATA_DIR = ROOT / "data" / "market"
OUTPUT_DIR = ROOT / "results" / "uranium_research"
CHART_DIR = OUTPUT_DIR / "graficos"

START_DATE = "2020-01-01"
IS_END = "2022-12-31"
OOS_START = "2023-01-01"

ASSETS = {
    "U-UN.TO": {
        "nome": "Sprott Physical Uranium Trust",
        "listagem": "TSX: U.UN",
        "moeda": "CAD",
        "papel": "Detentor de U3O8 físico (proxy do preço spot)",
        "principal": True,
        "inicio_valido": "2021-07-26",
        "nota": (
            "O Yahoo emenda o histórico da Uranium Participation Corp (antecessora) sem ajustar a troca "
            "de 1 ação UPC por 0,5 unidade SPUT: salto artificial de +118% em 26/07/2021 e 5 pregões "
            "congelados sem volume antes dele. A série é cortada em 26/07/2021 (primeiro pregão real da SPUT)."
        ),
    },
    "SRUUF": {
        "nome": "Sprott Physical Uranium Trust",
        "listagem": "OTCQX: SRUUF",
        "moeda": "USD",
        "papel": "Detentor de U3O8 físico (linha em USD)",
        "principal": False,
        "nota": "Negociação no OTCQX desde 22/07/2021.",
    },
    "LEU": {
        "nome": "Centrus Energy",
        "listagem": "NYSE American: LEU",
        "moeda": "USD",
        "papel": "Enriquecimento e combustível nuclear (LEU/HALEU)",
        "principal": True,
        "nota": "",
    },
    "PDN.AX": {
        "nome": "Paladin Energy",
        "listagem": "ASX: PDN",
        "moeda": "AUD",
        "papel": "Mineradora produtora (Langer Heinrich, Namíbia)",
        "principal": True,
        "nota": "Consolidação de ações 10:1 em 2024; a série do Yahoo vem ajustada por desdobramentos.",
    },
    "PALAF": {
        "nome": "Paladin Energy",
        "listagem": "OTCQX: PALAF",
        "moeda": "USD",
        "papel": "Mineradora produtora (linha em USD)",
        "principal": False,
        "nota": (
            "Linha OTC de baixa liquidez: cerca de 23% dos pregões abrem exatamente no fechamento anterior "
            "(abertura sem negócio). A execução em open[t+1] do backtest não é confiável nesta linha; use PDN.AX."
        ),
    },
    "CCJ": {
        "nome": "Cameco",
        "listagem": "NYSE: CCJ",
        "moeda": "USD",
        "papel": "Mineradora produtora integrada (mineração, conversão, Westinghouse)",
        "principal": True,
        "nota": "",
    },
    "URA": {
        "nome": "Global X Uranium ETF",
        "listagem": "NYSE Arca: URA",
        "moeda": "USD",
        "papel": "Referência setorial",
        "principal": False,
        "nota": "",
    },
    "SPY": {
        "nome": "SPDR S&P 500 ETF",
        "listagem": "NYSE Arca: SPY",
        "moeda": "USD",
        "papel": "Referência de mercado amplo",
        "principal": False,
        "nota": "",
    },
}

USD_LINES = ["SRUUF", "LEU", "PALAF", "CCJ", "URA", "SPY"]
PRIMARY = [t for t, meta in ASSETS.items() if meta["principal"]]

FUNDAMENTAL_FIELDS = [
    "currency",
    "financialCurrency",
    "marketCap",
    "enterpriseValue",
    "totalRevenue",
    "revenueGrowth",
    "grossMargins",
    "operatingMargins",
    "profitMargins",
    "ebitda",
    "totalCash",
    "totalDebt",
    "freeCashflow",
    "trailingPE",
    "forwardPE",
    "priceToBook",
    "enterpriseToRevenue",
    "enterpriseToEbitda",
    "sharesOutstanding",
    "beta",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
]


def fetch_or_cache(ticker: str) -> tuple[pd.DataFrame, dict]:
    parquet_path = DATA_DIR / f"{ticker}.parquet"
    audit = {"ticker": ticker, "origem": "cache_local" if parquet_path.exists() else "yahoo_finance"}
    if parquet_path.exists():
        clean = validate_ohlc(pd.read_parquet(parquet_path))
        audit.update(barras=len(clean), linhas_descartadas=0, barras_high_low_reparadas=0)
        return clean, audit

    raw = yf.download(ticker, start=START_DATE, auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.xs(ticker, axis=1, level=1)
    df = raw.rename(columns=lambda c: str(c).strip().lower()).copy()
    df = df[[c for c in ("open", "high", "low", "close", "volume") if c in df.columns]]
    before = len(df)
    df = df.dropna()
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    dropped = before - len(df)
    repaired_high = df["high"] < df[["open", "close"]].max(axis=1)
    repaired_low = df["low"] > df[["open", "close"]].min(axis=1)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    clean = validate_ohlc(df)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(parquet_path)
    audit.update(
        barras=len(clean),
        linhas_descartadas=int(dropped),
        barras_high_low_reparadas=int((repaired_high | repaired_low).sum()),
    )
    return clean, audit


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def buy_and_hold(data: pd.DataFrame, execution: ExecutionConfig) -> tuple[pd.DataFrame, dict]:
    """Compra no open da primeira barra e vende no close final, com o mesmo custo por ponta."""

    close = data["close"].astype(float)
    shares = execution.initial_capital * (1.0 - execution.cost_per_side) / float(data["open"].iloc[0])
    equity = shares * close
    equity.iloc[-1] *= 1.0 - execution.cost_per_side
    curve = pd.DataFrame({"equity": equity})
    curve["daily_return"] = curve["equity"].pct_change()
    curve.iloc[0, curve.columns.get_loc("daily_return")] = curve["equity"].iloc[0] / execution.initial_capital - 1.0
    curve["position"] = 1
    peak = curve["equity"].cummax().clip(lower=execution.initial_capital)
    curve["drawdown"] = curve["equity"].div(peak).sub(1.0)
    empty_trades = pd.DataFrame(columns=["net_return"])
    metrics = calculate_performance_metrics(
        curve, empty_trades, execution.initial_capital, execution.annual_risk_free_rate
    )
    return curve, metrics


def summarize(prefix: str, m: dict) -> dict:
    return {
        f"{prefix}_retorno_total_pct": round(m["total_return"] * 100, 2),
        f"{prefix}_cagr_pct": round(m["annualized_return"] * 100, 2),
        f"{prefix}_vol_anual_pct": round(m["annualized_volatility"] * 100, 2),
        f"{prefix}_sharpe": round(m["sharpe_ratio"], 3),
        f"{prefix}_sortino": round(m["sortino_ratio"], 3),
        f"{prefix}_max_dd_pct": round(m["max_drawdown"] * 100, 2),
    }


def git_state() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()

    return {"commit_sha": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current"), "dirty": bool(run("status", "--porcelain"))}


def fetch_fundamentals(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    info = tk.info or {}
    snapshot = {field: info.get(field) for field in FUNDAMENTAL_FIELDS}
    annual = {}
    try:
        stmt = tk.income_stmt
        for row in ("Total Revenue", "Gross Profit", "Operating Income", "Net Income"):
            if row in stmt.index:
                annual[row] = {str(col.date()): (None if pd.isna(v) else float(v)) for col, v in stmt.loc[row].items()}
    except Exception as err:
        annual["erro"] = str(err)
    return {"snapshot": snapshot, "dre_anual": annual}


def plot_charts(data: dict[str, pd.DataFrame], equities: dict[str, tuple[pd.DataFrame, pd.DataFrame]], corr: pd.DataFrame) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    common_start = max(data[t].index[0] for t in USD_LINES)
    closes = pd.DataFrame({t: data[t]["close"] for t in USD_LINES}).loc[common_start:].dropna()

    fig, ax = plt.subplots(figsize=(11, 5.5))
    (closes / closes.iloc[0] * 100).plot(ax=ax, logy=True, linewidth=1.4)
    ax.set_title(f"Preço normalizado (base 100 em {closes.index[0].date()}), linhas em USD, escala log")
    ax.set_ylabel("Índice (log)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "u1_preco_normalizado.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5))
    (closes / closes.cummax() - 1.0).mul(100).plot(ax=ax, linewidth=1.2)
    ax.set_title("Drawdown desde o topo anterior (%)")
    ax.set_ylabel("%")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "u2_drawdown.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=False)
    for ax, ticker in zip(axes.ravel(), PRIMARY):
        mom_curve, bh_curve = equities[ticker]
        ax.plot(mom_curve.index, mom_curve["equity"] / 1000, label="Momentum ATR", linewidth=1.3)
        ax.plot(bh_curve.index, bh_curve["equity"] / 1000, label="Buy & Hold", linewidth=1.3, alpha=0.8)
        ax.axvline(pd.Timestamp(OOS_START), color="grey", linestyle="--", linewidth=0.9)
        ax.set_yscale("log")
        ax.set_title(f"{ASSETS[ticker]['listagem']} ({ASSETS[ticker]['moeda']})")
        ax.set_ylabel("Patrimônio (mil, log)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Capital inicial 100 mil na moeda local; tracejado = início de 2023", fontsize=10)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "u3_momentum_vs_bh.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.values[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", color="white" if value > 0.6 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Correlação dos retornos diários (linhas em USD)")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "u4_correlacao.png", dpi=130)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    data: dict[str, pd.DataFrame] = {}
    data_audit = []
    for ticker in ASSETS:
        df, audit = fetch_or_cache(ticker)
        valid_start = ASSETS[ticker].get("inicio_valido")
        if valid_start:
            audit["barras_excluidas_antes_de_inicio_valido"] = int((df.index < valid_start).sum())
            df = df.loc[valid_start:]
            audit["barras"] = len(df)
        audit["pct_barras_ohlc_planas"] = round(float(((df.open == df.high) & (df.high == df.low) & (df.low == df.close)).mean()) * 100, 2)
        audit["pct_open_igual_fechamento_anterior"] = round(float((df.open == df.close.shift()).mean()) * 100, 2)
        audit["maior_variacao_diaria_abs_pct"] = round(float(df.close.pct_change().abs().max()) * 100, 2)
        audit["primeira_barra"] = str(df.index[0].date())
        audit["ultima_barra"] = str(df.index[-1].date())
        audit["sha256_parquet"] = sha256_file(DATA_DIR / f"{ticker}.parquet")
        data[ticker] = df
        data_audit.append(audit)
        print(f"[{ticker}] {audit['barras']} barras {audit['primeira_barra']} → {audit['ultima_barra']}")

    metric_rows, period_rows = [], []
    equities: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for ticker, df in data.items():
        result = run_backtest(df, strategy, execution)
        bh_curve, bh_metrics = buy_and_hold(df, execution)
        equities[ticker] = (result.equity_curve, bh_curve)
        result.equity_curve.to_csv(OUTPUT_DIR / f"{ticker}_equity.csv")
        result.trades.to_csv(OUTPUT_DIR / f"{ticker}_trades.csv", index=False)
        m = result.metrics
        metric_rows.append({
            "ticker": ticker,
            "listagem": ASSETS[ticker]["listagem"],
            "moeda": ASSETS[ticker]["moeda"],
            "barras": m["bars"],
            "operacoes": m["total_trades"],
            "acerto_pct": round(m["win_rate"] * 100, 2),
            "profit_factor": round(m["profit_factor"], 2),
            "exposicao_pct": round(m["exposure"] * 100, 1),
            **summarize("mom", m),
            **summarize("bh", bh_metrics),
            "mom_skew": round(m["return_skewness"], 3),
            "mom_kurt": round(m["return_kurtosis"], 3),
        })

        for label, start, end in (("2020-2022", None, IS_END), ("2023-hoje", OOS_START, None)):
            sub = df.loc[start:end]
            if len(sub) < strategy.momentum_window + strategy.atr_window + 5:
                continue
            sub_result = run_backtest(df, strategy, execution, trade_start=start, trade_end=end)
            _, sub_bh = buy_and_hold(sub, execution)
            period_rows.append({
                "ticker": ticker,
                "periodo": label,
                "primeira_barra": str(sub.index[0].date()),
                "barras": len(sub),
                "operacoes": sub_result.metrics["total_trades"],
                **summarize("mom", sub_result.metrics),
                **summarize("bh", sub_bh),
            })

    metrics = pd.DataFrame(metric_rows)
    periods = pd.DataFrame(period_rows)
    metrics.to_csv(OUTPUT_DIR / "uranio_metricas_comparativas.csv", index=False)
    periods.to_csv(OUTPUT_DIR / "uranio_metricas_por_periodo.csv", index=False)

    stress = run_stress_matrix(data, {"uranio": list(ASSETS)}, strategy_config=strategy)
    stress_view = stress[["ticker", "scenario", "cost_per_side", "stop_slippage", "total_trades", "total_return", "sharpe_ratio", "max_drawdown"]].copy()
    stress_view.to_csv(OUTPUT_DIR / "uranio_stress.csv", index=False)

    primary = metrics.set_index("ticker").loc[PRIMARY]
    sharpe_std = float(primary["mom_sharpe"].std(ddof=1))
    benchmark_sr = expected_maximum_sharpe(sharpe_std, len(PRIMARY))
    dsr_rows = []
    for ticker in PRIMARY:
        row = primary.loc[ticker]
        dsr_rows.append({
            "ticker": ticker,
            "sharpe_observado": float(row["mom_sharpe"]),
            "sharpe_benchmark_multiplos_testes": round(benchmark_sr, 4),
            "dsr_probabilidade": round(
                deflated_sharpe_probability(
                    float(row["mom_sharpe"]),
                    benchmark_sr,
                    n_observations=int(row["barras"]),
                    skewness=float(row["mom_skew"]),
                    kurtosis=float(row["mom_kurt"]),
                ),
                4,
            ),
        })
    dsr = pd.DataFrame(dsr_rows)
    dsr.to_csv(OUTPUT_DIR / "uranio_dsr.csv", index=False)

    common_start = max(data[t].index[0] for t in USD_LINES)
    returns = pd.DataFrame({t: data[t]["close"] for t in USD_LINES}).loc[common_start:].pct_change().dropna()
    corr = returns.corr()
    corr.to_csv(OUTPUT_DIR / "uranio_correlacao.csv")
    beta_rows = []
    for ticker in USD_LINES:
        row = {"ticker": ticker}
        for ref in ("URA", "SPY"):
            cov = returns[[ticker, ref]].cov().iloc[0, 1]
            row[f"beta_{ref}"] = round(cov / returns[ref].var(), 3)
        row["vol_anual_pct"] = round(returns[ticker].std() * np.sqrt(252) * 100, 2)
        beta_rows.append(row)
    betas = pd.DataFrame(beta_rows)
    betas.to_csv(OUTPUT_DIR / "uranio_beta.csv", index=False)

    liquidity_rows = []
    for ticker, df in data.items():
        recent = df.iloc[-63:]
        liquidity_rows.append({
            "ticker": ticker,
            "moeda": ASSETS[ticker]["moeda"],
            "volume_financeiro_medio_63d": round(float((recent["close"] * recent["volume"]).mean()), 0),
            "dias_sem_volume_63d": int((recent["volume"] <= 0).sum()),
            "ultimo_fechamento": round(float(df["close"].iloc[-1]), 4),
        })
    liquidity = pd.DataFrame(liquidity_rows)
    liquidity.to_csv(OUTPUT_DIR / "uranio_liquidez.csv", index=False)

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fundamentals = {"fonte": "Yahoo Finance via yfinance (dados de provedor, sem conferência com demonstrações oficiais)", "coletado_em_utc": fetched_at, "ativos": {}}
    for ticker in PRIMARY:
        try:
            fundamentals["ativos"][ticker] = fetch_fundamentals(ticker)
        except Exception as err:
            fundamentals["ativos"][ticker] = {"erro": str(err)}
    (OUTPUT_DIR / "uranio_fundamentos_snapshot.json").write_text(json.dumps(fundamentals, indent=2, ensure_ascii=False), encoding="utf-8")

    plot_charts(data, equities, corr)

    manifest = {
        "estudo": "cadeia_uranio",
        "gerado_em_utc": fetched_at,
        "script": "scripts/analisar_uranio.py",
        "sha256_script": sha256_file(Path(__file__)),
        "git": git_state(),
        "ambiente": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "yfinance": yf.__version__},
        "estrategia": {"momentum_window": 20, "atr_window": 14, "stop_multiplier": 2.5, "origem_parametros": "padrão do repositório, sem otimização nestes ativos"},
        "execucao": {"custo_por_ponta": 0.0015, "capital_inicial": 100_000.0, "sinal": "close[t]", "execucao": "open[t+1]"},
        "cortes": {"is_ate": IS_END, "oos_desde": OOS_START, "classificacao": "retrospective_pseudo_oos"},
        "dsr": {"numero_de_testes": len(PRIMARY), "desvio_dos_sharpes": round(sharpe_std, 4), "ativos": PRIMARY},
        "dados": data_audit,
        "governanca": {"paper_only": True, "shadow_mode": True, "aprovado": False, "promotion_allowed": False, "pbo": None, "pbo_motivo": "not_implemented_in_repository"},
        "ativos": ASSETS,
    }
    (OUTPUT_DIR / "manifesto_uranio.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    pd.set_option("display.width", 220)
    print("\nMÉTRICAS (período completo):")
    print(metrics.drop(columns=["listagem"]).to_string(index=False))
    print("\nPOR PERÍODO:")
    print(periods.to_string(index=False))
    print("\nDSR:")
    print(dsr.to_string(index=False))
    print("\nESTRESSE:")
    print(stress_view.to_string(index=False))
    print("\nCORRELAÇÃO:")
    print(corr.round(2).to_string())
    print("\nBETA:")
    print(betas.to_string(index=False))
    print("\nLIQUIDEZ:")
    print(liquidity.to_string(index=False))


if __name__ == "__main__":
    main()
