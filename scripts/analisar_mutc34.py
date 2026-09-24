"""Análise quantitativa e fundamentalista de Micron Technology (MU / MUTC34).

Executa o motor Momentum ATR e métricas comparativas com benchmarks e pares de semicondutores,
calcula a paridade cambial do BDR MUTC34 na B3 e analisa o enquadramento quantitativo
da ação dentro do portfólio multi-sleeve do laboratório iitauquant.
"""

from __future__ import annotations

import json
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
from strategies.momentum_atr import (
    MomentumATRConfig,
    average_true_range,
    validate_ohlc,
)

DATA_DIR = ROOT / "data" / "market"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT / "results" / "micron_research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_or_cache(ticker: str, start_date: str = "2020-01-01") -> pd.DataFrame:
    cache_path = DATA_DIR / f"{ticker.replace('^', '').replace('=', '')}.csv"
    if cache_path.exists():
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
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
    clean.to_csv(cache_path)
    print(f"[{ticker}] Salvo no cache: {len(clean)} barras")
    return clean


def main():
    tickers = ["MU", "MUTC34.SA", "SMH", "SOXX", "NVDA", "SPY", "QQQ"]
    strategy = MomentumATRConfig(momentum_window=20, atr_window=14, stop_multiplier=2.5)
    execution = ExecutionConfig(cost_per_side=0.0015, initial_capital=100_000.0)

    rows = []
    data_dict = {}

    for t in tickers:
        try:
            df = fetch_or_cache(t)
            data_dict[t] = df
        except Exception as e:
            print(f"Erro em {t}: {e}")
            continue

        res = run_backtest(df, strategy, execution)
        m = res.metrics

        # Salvar curves e trades
        safe_name = t.replace(".SA", "").replace("^", "")
        res.equity_curve.to_csv(OUTPUT_DIR / f"{safe_name}_equity.csv")
        res.trades.to_csv(OUTPUT_DIR / f"{safe_name}_trades.csv", index=False)

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
            "exposure_pct": round(m["exposure"] * 100, 1),
            "bh_ret_pct": round(bh_ret * 100, 2),
            "bh_cagr_pct": round(cagr * 100, 2),
            "bh_vol_pct": round(ann_vol * 100, 2),
            "bh_sharpe": round(sharpe_bh, 3),
            "bh_max_dd_pct": round(max_dd_bh * 100, 2),
        })

    res_df = pd.DataFrame(rows)
    res_df.to_csv(OUTPUT_DIR / "micron_comparative_metrics.csv", index=False)
    print("\n" + "=" * 80)
    print("MÉTRICAS COMPARATIVAS QUANTITATIVAS (MICRON / BENCHMARKS):")
    print(res_df.to_string(index=False))

    # --- Análise de Paridade BDR MUTC34 vs MU ---
    df_mutc = data_dict.get("MUTC34.SA")
    df_mu = data_dict.get("MU")
    fx_raw = fetch_or_cache("USDBRL=X")
    usd_brl = float(fx_raw["close"].iloc[-1])

    mutc_close = float(df_mutc["close"].iloc[-1])
    mu_close = float(df_mu["close"].iloc[-1])

    bdr_ratio = 6.0  # 1 ação ordinária MU = 6 BDRs MUTC34
    theoretical_bdr = (mu_close * usd_brl) / bdr_ratio
    parity_spread_pct = ((mutc_close / theoretical_bdr) - 1.0) * 100.0

    # ATR e Stops
    atr_mutc = float(average_true_range(df_mutc, 14).iloc[-1])
    atr_mu = float(average_true_range(df_mu, 14).iloc[-1])

    stop_25_atr = mutc_close - 2.5 * atr_mutc
    stop_20_atr = mutc_close - 2.0 * atr_mutc
    stop_15_atr = mutc_close - 1.5 * atr_mutc

    # Médias Móveis
    mutc_sma20 = float(df_mutc["close"].rolling(20).mean().iloc[-1])
    mutc_sma50 = float(df_mutc["close"].rolling(50).mean().iloc[-1])
    mutc_sma200 = float(df_mutc["close"].rolling(200).mean().iloc[-1])

    mu_sma20 = float(df_mu["close"].rolling(20).mean().iloc[-1])
    mu_sma50 = float(df_mu["close"].rolling(50).mean().iloc[-1])
    mu_sma200 = float(df_mu["close"].rolling(200).mean().iloc[-1])

    # Momentum 12-1 (Sleeve 2 do quant_fund)
    if len(df_mu) >= 252:
        p_t1 = float(df_mu["close"].iloc[-21])
        p_t12 = float(df_mu["close"].iloc[-252])
        mom_12_1 = (p_t1 / p_t12) - 1.0
        rev_1m = (mu_close / p_t1) - 1.0
    else:
        mom_12_1 = 0.0
        rev_1m = 0.0

    # Retorno 1 ano, 52w high / low
    high_52w = float(df_mutc["high"].rolling(252).max().iloc[-1])
    low_52w = float(df_mutc["low"].rolling(252).min().iloc[-1])

    micron_summary = {
        "ticker_bdr": "MUTC34.SA",
        "ticker_us": "MU",
        "date": str(df_mutc.index[-1])[:10],
        "mutc_close": round(mutc_close, 2),
        "mu_close": round(mu_close, 2),
        "usd_brl": round(usd_brl, 4),
        "bdr_ratio": bdr_ratio,
        "theoretical_bdr": round(theoretical_bdr, 2),
        "parity_spread_pct": round(parity_spread_pct, 2),
        "atr14_bdr": round(atr_mutc, 2),
        "atr14_bdr_pct": round((atr_mutc / mutc_close) * 100, 2),
        "stop_25_atr": round(stop_25_atr, 2),
        "stop_20_atr": round(stop_20_atr, 2),
        "stop_15_atr": round(stop_15_atr, 2),
        "mutc_sma20": round(mutc_sma20, 2),
        "mutc_sma50": round(mutc_sma50, 2),
        "mutc_sma200": round(mutc_sma200, 2),
        "mu_sma20": round(mu_sma20, 2),
        "mu_sma50": round(mu_sma50, 2),
        "mu_sma200": round(mu_sma200, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "dist_high_52w_pct": round(((mutc_close / high_52w) - 1.0) * 100, 2),
        "momentum_12_1_mu_pct": round(mom_12_1 * 100, 2),
        "reversal_1m_mu_pct": round(rev_1m * 100, 2),
    }

    with open(OUTPUT_DIR / "micron_summary.json", "w", encoding="utf-8") as f:
        json.dump(micron_summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("RESUMO DA POSIÇÃO E PARIDADE DO BDR MUTC34:")
    for k, v in micron_summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
