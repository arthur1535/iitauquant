"""Análise quantitativa e fundamentalista de Taiwan Semiconductor (TSM / TSMC34)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.engine import ExecutionConfig, run_backtest
from strategies.momentum_atr import MomentumATRConfig, validate_ohlc

DATA_DIR = ROOT / "data" / "market"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT / "results" / "tsmc_research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_or_cache(ticker: str, start_date: str = "2020-01-01") -> pd.DataFrame:
    parquet_path = DATA_DIR / f"{ticker}.parquet"
    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            clean = validate_ohlc(df)
            print(f"[{ticker}] Carregado do cache: {len(clean)} barras")
            return clean
        except Exception:
            pass

    print(f"[{ticker}] Baixando dados...")
    raw = yf.download(ticker, start=start_date, auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(1):
            raw = raw.xs(ticker, axis=1, level=1)
        elif ticker in raw.columns.get_level_values(0):
            raw = raw[ticker]
    df = raw.rename(columns=lambda c: str(c).strip().lower()).copy()
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[cols].dropna()
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    clean = validate_ohlc(df)
    clean.to_parquet(parquet_path)
    print(f"[{ticker}] Salvo no cache: {len(clean)} barras")
    return clean


def main():
    tickers = ["TSM", "TSMC34.SA", "SMH", "NVDA", "SPY"]
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    rows = []
    for t in tickers:
        try:
            df = fetch_or_cache(t)
        except Exception as e:
            print(f"Erro em {t}: {e}")
            continue

        res = run_backtest(df, strategy, execution)
        m = res.metrics

        # Salvar curves e trades
        res.equity_curve.to_csv(OUTPUT_DIR / f"{t}_equity.csv")
        res.trades.to_csv(OUTPUT_DIR / f"{t}_trades.csv", index=False)

        close = df["close"]
        bh_ret = (close.iloc[-1] / close.iloc[0]) - 1.0
        n_years = len(close) / 252.0
        cagr = (1.0 + bh_ret) ** (1.0 / n_years) - 1.0 if n_years > 0 and (1.0 + bh_ret) > 0 else -1.0
        daily_ret = close.pct_change().dropna()
        ann_vol = daily_ret.std() * np.sqrt(252)
        sharpe_bh = (cagr - 0.03) / ann_vol if ann_vol > 0 else 0.0
        rolling_max = close.cummax()
        dd = (close - rolling_max) / rolling_max
        max_dd_bh = dd.min()

        rows.append({
            "ticker": t,
            "bars": m["bars"],
            "trades": m["total_trades"],
            "win_rate_pct": round(m["win_rate"] * 100, 2),
            "mom_ret_pct": round(m["total_return"] * 100, 2),
            "mom_cagr_pct": round(m["annualized_return"] * 100, 2),
            "mom_vol_pct": round(m["annualized_volatility"] * 100, 2),
            "mom_sharpe": round(m["sharpe_ratio"], 3),
            "mom_max_dd_pct": round(m["max_drawdown"] * 100, 2),
            "mom_pf": round(m["profit_factor"], 2),
            "bh_ret_pct": round(bh_ret * 100, 2),
            "bh_cagr_pct": round(cagr * 100, 2),
            "bh_vol_pct": round(ann_vol * 100, 2),
            "bh_sharpe": round(sharpe_bh, 3),
            "bh_max_dd_pct": round(max_dd_bh * 100, 2),
        })

    res_df = pd.DataFrame(rows)
    res_df.to_csv(OUTPUT_DIR / "tsmc_comparative_metrics.csv", index=False)
    print("\n" + "=" * 80)
    print("MÉTRICAS COMPARATIVAS QUANTITATIVAS:")
    print(res_df.to_string(index=False))


if __name__ == "__main__":
    main()
