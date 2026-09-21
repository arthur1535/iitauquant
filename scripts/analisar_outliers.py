"""Script para analisar outliers de alto crescimento e assimetria de retorno."""

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
OUTPUT_DIR = ROOT / "results" / "outliers_research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTLIER_TICKERS = {
    "PLTR": "Enterprise AI & Inteligência Governamental",
    "ASTS": "Telecom Espacial Direto ao Celular (Direct-to-Cell)",
    "VRT": "Infraestrutura Crítica & Refrigeração de Data Centers de IA",
    "APP": "AdTech & Algoritmos de Monetização de Apps (Axon 2.0)",
    "MSTR": "Proxy Alavancada de Bitcoin / Ativo de Reserva",
    "CELH": "Bebidas Energéticas Funcionais / Hipercrescimento Varejo",
    "SMCI": "Servidores de Computação Acelerada para IA",
    "HIMS": "Telemedicina Direta ao Consumidor & GLP-1",
    "FUTU": "Fintech & Corretora de Ações Digitais (China/HK/Global)",
}


def fetch_or_load(ticker: str, start_date: str = "2020-01-01") -> pd.DataFrame | None:
    parquet_path = DATA_DIR / f"{ticker}.parquet"
    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            if not isinstance(df.index, pd.DatetimeIndex):
                date_col = next((c for c in ("date", "datetime", "timestamp", "Date") if c in df.columns), None)
                if date_col is not None:
                    df.index = pd.to_datetime(df.pop(date_col))
                elif "index" in df.columns:
                    df.index = pd.to_datetime(df.pop("index"))
            clean = validate_ohlc(df)
            print(f"[{ticker}] Carregado do cache ({len(clean)} barras)")
            return clean
        except Exception:
            pass

    print(f"[{ticker}] Baixando do Yahoo Finance...")
    try:
        raw = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
        if raw.empty:
            print(f"[{ticker}] Retorno vazio!")
            return None

        if isinstance(raw.columns, pd.MultiIndex):
            if ticker in raw.columns.get_level_values(1):
                raw = raw.xs(ticker, axis=1, level=1)
            elif ticker in raw.columns.get_level_values(0):
                raw = raw[ticker]

        df = raw.rename(columns=lambda c: str(c).strip().lower()).copy()
        df = df.loc[df.index.notna()].sort_index()

        cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        df = df[cols].dropna()

        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"] = df[["low", "open", "close"]].min(axis=1)

        clean = validate_ohlc(df[["open", "high", "low", "close", "volume"]])
        clean.to_parquet(parquet_path)
        print(f"[{ticker}] Salvo e validado ({len(clean)} barras)")
        return clean
    except Exception as e:
        print(f"[{ticker}] Erro: {e}")
        return None


def run_outliers_analysis():
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    records = []

    for ticker, tese in OUTLIER_TICKERS.items():
        df = fetch_or_load(ticker)
        if df is None or len(df) < 50:
            continue

        # 1. Backtest Momentum ATR
        res = run_backtest(df, strategy, execution)
        m = res.metrics

        # 2. Buy & Hold benchmark do próprio ativo
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

        records.append({
            "ticker": ticker,
            "tese": tese,
            "bars": m["bars"],
            "bh_total_return_pct": round(bh_ret * 100, 2),
            "bh_cagr_pct": round(cagr * 100, 2),
            "bh_max_dd_pct": round(max_dd_bh * 100, 2),
            "bh_sharpe": round(sharpe_bh, 3),
            "mom_total_return_pct": round(m["total_return"] * 100, 2),
            "mom_cagr_pct": round(m["annualized_return"] * 100, 2),
            "mom_vol_pct": round(m["annualized_volatility"] * 100, 2),
            "mom_sharpe": round(m["sharpe_ratio"], 3),
            "mom_max_dd_pct": round(m["max_drawdown"] * 100, 2),
            "mom_win_rate_pct": round(m["win_rate"] * 100, 2),
            "mom_profit_factor": round(m["profit_factor"], 2),
            "trades": m["total_trades"],
        })

    df_outliers = pd.DataFrame(records).sort_values(by="bh_total_return_pct", ascending=False).reset_index(drop=True)
    df_outliers.to_csv(OUTPUT_DIR / "outliers_metrics.csv", index=False)

    print("\n" + "=" * 90)
    print("OUTLIERS DE ALTO CRESCIMENTO E RETORNO ASSIMÉTRICO (2020 - 2026):")
    print(df_outliers[["ticker", "bh_total_return_pct", "bh_max_dd_pct", "mom_total_return_pct", "mom_max_dd_pct", "mom_sharpe", "mom_profit_factor"]].to_string(index=False))

    return df_outliers


if __name__ == "__main__":
    run_outliers_analysis()
