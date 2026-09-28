"""Reproduce the exploratory B3 beta/liquidity snapshot; no trading recommendations.

Run from the repository root:
  .venv\\Scripts\\python.exe results/bets_research/market/collect_market_snapshot.py

Yahoo adjusted closes are used for simple total-return proxies. ADV is a proxy
using Yahoo Close * Volume with auto_adjust=False, not exchange turnover/VWAP.
Historical data can be revised by the provider; CSV hashes freeze this download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


TICKERS = ["LREN3", "CEAB3", "RIAA3", "MGLU3", "AZZA3", "VIVA3", "MULT3", "IGTI11", "ALOS3", "B3SA3", "BPAC11", "ITUB4", "BBDC4"]
SECTORS = {
    "LREN3": "Varejo de vestuario", "CEAB3": "Varejo de vestuario",
    "RIAA3": "Varejo de vestuario", "MGLU3": "Varejo de duraveis",
    "AZZA3": "Moda e calcados", "VIVA3": "Joalheria",
    "MULT3": "Shoppings", "IGTI11": "Shoppings", "ALOS3": "Shoppings",
    "B3SA3": "Infraestrutura de mercado", "BPAC11": "Banco e investimentos",
    "ITUB4": "Banco", "BBDC4": "Banco",
}
SOURCES = [
    {"title": "B3 previa IBOV: tickers", "url": "https://sistemaswebb3-listados.b3.com.br/indexPage/preview/IBOV?language=pt-br"},
    {"title": "B3 calendario de resultados 2T2026", "url": "https://borainvestir.b3.com.br/objetivos-financeiros/investir-melhor/temporada-de-balancos-confira-o-calendario-de-divulgacao-dos-resultados-do-segundo-trimestre-2/"},
    {"title": "RI Guararapes: GUAR3 muda para RIAA3 em 2026-02-05", "url": "https://filemanager-cdn.mziq.com/published/0c51b75c-1d63-4db0-85ed-6a34ac67fccc/21ea0526-a74a-4ab8-93f7-a3ee5a9329ca_comunicado_ao_mercado_novo_codigo_de_negociacao.pdf"},
    {"title": "B3: BDRs INBR32, ROXO34, XPBR31 em 2026", "url": "https://borainvestir.b3.com.br/tipos-de-investimentos/renda-variavel/bdrs/mercado-brasileiro-ja-negocia-mais-de-r-1-bi-em-bdrs-por-dia/"},
    {"title": "B3: conversao SOMA3 e ARZZ3 para AZZA3", "url": "https://www.b3.com.br/data/files/FE/11/55/95/09BE09105FE89209AC094EA8/OC%20012-2024-VNC%20Tratamento%20Carteiras%20de%20%C3%8Dndices%20da%20B3%20-%20Evento%20de%20Incorpora%C3%A7%C3%A3o%20do%20Grupo%20de%20Moda%20Soma%20pela%20Arezzo_PT.pdf"},
]


def ols_hac(y: np.ndarray, market: np.ndarray, lags: int = 5) -> dict:
    """OLS intercept and Newey-West Bartlett HAC with n/(n-k) correction."""
    x = np.column_stack([np.ones(len(market)), market])
    coef = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ coef
    xu = x * residual[:, None]
    meat = xu.T @ xu
    for lag in range(1, min(lags, len(y) - 1) + 1):
        gamma = xu[lag:].T @ xu[:-lag]
        meat += (1 - lag / (lags + 1)) * (gamma + gamma.T)
    bread = np.linalg.inv(x.T @ x)
    covariance = bread @ meat @ bread * len(y) / (len(y) - x.shape[1])
    beta = float(coef[1])
    se = float(np.sqrt(max(0.0, covariance[1, 1])))
    sst = float(np.sum((y - y.mean()) ** 2))
    return {"beta_ibov_252": beta, "beta_hac_se": se,
            "beta_ci95_low": beta - 1.959963984540054 * se,
            "beta_ci95_high": beta + 1.959963984540054 * se,
            "r_squared": 1 - float(residual @ residual) / sst,
            "alpha_daily": float(coef[0])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cutoff", default="2026-09-25")
    ap.add_argument("--start", default="2024-08-01")
    ap.add_argument("--outdir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    out = args.outdir
    out.mkdir(parents=True, exist_ok=True)
    cutoff = pd.Timestamp(args.cutoff)
    if cutoff > pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize():
        raise ValueError("Cutoff cannot be in the future.")
    symbols = [f"{ticker}.SA" for ticker in TICKERS] + ["^BVSP"]
    downloaded_at = datetime.now(timezone.utc).isoformat()
    data = yf.download(symbols, start=args.start,
                       end=(cutoff + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                       auto_adjust=False, actions=True, repair=False,
                       progress=False, threads=False, keepna=True)
    if data.empty:
        raise RuntimeError("No Yahoo data; do not synthesize a snapshot.")
    data.index = pd.to_datetime(data.index).tz_localize(None)
    data = data.loc[data.index <= cutoff]
    raw_path = out / "yahoo_daily_snapshot.csv"
    data.to_csv(raw_path, index_label="date", float_format="%.12g")
    adj = data["Adj Close"].rename(columns=lambda s: s.removesuffix(".SA"))
    raw = data["Close"].rename(columns=lambda s: s.removesuffix(".SA"))
    volume = data["Volume"].rename(columns=lambda s: s.removesuffix(".SA"))
    returns = adj.pct_change(fill_method=None)
    adj.to_csv(out / "adjusted_close.csv", index_label="date", float_format="%.12g")
    returns.to_csv(out / "daily_returns.csv", index_label="date", float_format="%.12g")
    rows = []
    for ticker in TICKERS:
        pair = returns[[ticker, "^BVSP"]].dropna().tail(252)
        money_volume = (raw[ticker] * volume[ticker]).dropna().tail(60)
        all_prices = adj[ticker].dropna()
        row = {"ticker": ticker, "sector": SECTORS[ticker],
               "provider": "Yahoo Finance via yfinance", "requested_cutoff": args.cutoff,
               "first_price_date": str(all_prices.index.min().date()) if len(all_prices) else None,
               "last_price_date": str(all_prices.index.max().date()) if len(all_prices) else None,
               "n_daily_pairs": len(pair),
               "beta_window_start": str(pair.index.min().date()) if len(pair) else None,
               "beta_window_end": str(pair.index.max().date()) if len(pair) else None,
               "adv60_proxy_brl": float(money_volume.mean()) if len(money_volume) else None,
               "adv_nobs": len(money_volume),
               "adv_window_start": str(money_volume.index.min().date()) if len(money_volume) else None,
               "adv_window_end": str(money_volume.index.max().date()) if len(money_volume) else None,
               "adv_pass_20m": bool(len(money_volume) == 60 and money_volume.mean() >= 20_000_000),
               "stale_against_ibov": bool(not len(all_prices) or all_prices.index.max() < adj["^BVSP"].dropna().index.max())}
        if len(pair) >= 200:
            row.update(ols_hac(pair[ticker].to_numpy(), pair["^BVSP"].to_numpy()))
            row["annual_vol_252"] = float(pair[ticker].std(ddof=1) * np.sqrt(252))
        else:
            row["note"] = "Insufficient 200 daily paired observations; beta deliberately omitted."
        weekly_prices = adj[[ticker, "^BVSP"]].resample("W-FRI").last()
        weekly_prices = weekly_prices.loc[weekly_prices.index <= cutoff]
        weekly = weekly_prices.pct_change(fill_method=None).dropna().tail(52)
        row["n_weekly_pairs"] = len(weekly)
        if len(weekly) >= 40:
            row["beta_weekly_52"] = float(weekly[ticker].cov(weekly["^BVSP"]) / weekly["^BVSP"].var())
        price = adj[ticker].dropna()
        if len(price) >= 21:
            row["momentum20"] = float(price.iloc[-1] / price.iloc[-21] - 1)
        if len(price) >= 253:
            row["momentum_12_1"] = float(price.iloc[-22] / price.iloc[-253] - 1)
        if len(price) >= 201:
            row["above_ma200"] = bool(price.iloc[-1] > price.iloc[-200:].mean())
        sigma60 = returns[ticker].dropna().tail(60)
        if len(sigma60) == 60:
            row["annual_vol60"] = float(sigma60.std(ddof=1) * np.sqrt(252))
            if row["annual_vol60"] > 0 and "momentum_12_1" in row:
                row["score_mom12_1_vol60"] = row["momentum_12_1"] / row["annual_vol60"]
        row["beta_pass_07_18"] = bool(0.7 <= row.get("beta_ibov_252", float("nan")) <= 1.8)
        row["technical_pass"] = bool(row.get("above_ma200", False)
                                      and row.get("momentum20", -1) > 0
                                      and row.get("momentum_12_1", -1) > 0)
        row["technical_liquidity_beta_eligible"] = bool(row["technical_pass"]
                                                        and row["adv_pass_20m"]
                                                        and row["beta_pass_07_18"]
                                                        and not row["stale_against_ibov"])
        splits = data.get("Stock Splits", pd.DataFrame()).get(ticker + ".SA")
        if splits is not None and len(money_volume):
            row["split_events_adv_window"] = int((splits.loc[money_volume.index] > 0).sum())
        rows.append(row)
    snapshot = pd.DataFrame(rows)
    eligible = snapshot["technical_liquidity_beta_eligible"]
    snapshot["technical_eligible_rank"] = snapshot.loc[eligible, "score_mom12_1_vol60"].rank(ascending=False, method="first")
    snapshot["technical_top6_only_not_trade_signal"] = snapshot["technical_eligible_rank"].le(6)
    snapshot.to_csv(out / "market_snapshot.csv", index=False, float_format="%.10g")
    records = json.loads(snapshot.to_json(orient="records"))
    (out / "market_snapshot.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "downloaded_at_utc": downloaded_at, "requested_cutoff": args.cutoff,
        "source": "Yahoo Finance chart service via yfinance",
        "benchmark": "^BVSP adjusted close; Ibovespa total return index proxy",
        "python": platform.python_version(), "pandas": pd.__version__,
        "numpy": np.__version__, "yfinance": yf.__version__, "symbols": symbols,
        "actual_benchmark_last_date": str(adj["^BVSP"].dropna().index.max().date()),
        "beta": "OLS with intercept on last 252 paired simple daily returns; minimum 200; no filling missing prices; raw returns not excess returns.",
        "uncertainty": "95% asymptotic normal CI, Newey-West HAC Bartlett lags=5 with n/(n-2) finite sample correction; implemented directly in numpy.",
        "liquidity": "60-observation mean of Close * Volume, auto_adjust=False: estimated BRL turnover, not official financial volume. Never use Adj Close * Volume.",
        "weekly_beta": "Last 52 Friday-to-Friday simple returns, minimum 40; no market-timing interpretation.",
        "technical_screen": "Momentum20=C[t]/C[t-20]-1; momentum12_1=C[t-21]/C[t-252]-1; sigma60=std(last60 daily returns,ddof=1)*sqrt252; score=momentum12_1/sigma60. Eligible: both momentums>0, close>SMA200, ADV60>=BRL20m, 0.7<=beta252<=1.8, current data. Rank top6 among eligible. Does not include betting regulatory/attention regime and is NOT a trade signal.",
        "corporate_actions": "Current RIAA3 replaces GUAR3 effective 2026-02-05; Yahoo historical series under current symbol used as returned, no custom splice. AZZA3 combines predecessor corporate history in provider data; production use needs corporate action audit.",
        "limitations": ["Beta measures broad market covariance, not domestic investment-flow sensitivity or causal exposure to betting regulation.", "Survivorship and point-in-time instrument-universe reconstruction still required for strategy backtesting.", "Public Yahoo data are exploratory; reconcile with B3 before execution.", "No claim that a liquid candidate meets the strategy's full entry conditions."],
        "primary_sources": SOURCES,
        "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob("*.csv")},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ["ticker", "last_price_date", "n_daily_pairs", "beta_ibov_252", "beta_ci95_low", "beta_ci95_high", "adv60_proxy_brl", "adv_pass_20m", "beta_weekly_52", "above_ma200", "momentum20", "momentum_12_1", "technical_top6_only_not_trade_signal"]
    print(snapshot.reindex(columns=cols).to_string(index=False))


if __name__ == "__main__":
    main()
