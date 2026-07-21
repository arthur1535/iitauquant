from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from .core import DATA_ROOT, Manifest, canonical_ticker, ensure_directories, utc_now, write_dataset, yahoo_ticker


PRICE_COLUMNS = ["date", "month_end", "ticker", "provider_ticker", "close", "adjusted_close", "volume", "return"]


def _ticker_frame(download: pd.DataFrame, ticker: str, ticker_count: int) -> pd.DataFrame:
    if isinstance(download.columns, pd.MultiIndex):
        level0 = set(map(str, download.columns.get_level_values(0)))
        if ticker in level0:
            return download[ticker].copy()
        level1 = set(map(str, download.columns.get_level_values(1)))
        if ticker in level1:
            return download.xs(ticker, axis=1, level=1).copy()
    if ticker_count == 1:
        return download.copy()
    return pd.DataFrame()


def collect_adjusted_prices(
    tickers: Iterable[str],
    start: str,
    end: str | None = None,
    *,
    refresh: bool = False,
    batch_size: int = 100,
    output_name: str = "precos_mensais.csv",
) -> tuple[pd.DataFrame, list[str]]:
    """Coleta diario, preserva Close e Adj Close, e fecha cada mes no ultimo pregao."""
    ensure_directories()
    canonical = list(dict.fromkeys(canonical_ticker(item) for item in tickers))
    provider_map = {item: yahoo_ticker(item) for item in canonical}
    output_path = DATA_ROOT / "processed" / output_name
    if output_path.exists() and not refresh:
        cached = pd.read_csv(output_path, parse_dates=["date", "month_end"])
        return cached, []

    parts: list[pd.DataFrame] = []
    failed: list[str] = []
    for offset in range(0, len(canonical), batch_size):
        batch = canonical[offset : offset + batch_size]
        providers = [provider_map[item] for item in batch]
        try:
            downloaded = yf.download(
                providers,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=False,
                actions=False,
                repair=True,
                keepna=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=30,
            )
        except Exception as exc:
            Manifest().record(event="prices_download", status="failed", tickers=batch, error=str(exc))
            failed.extend(batch)
            continue

        for original in batch:
            provider = provider_map[original]
            one = _ticker_frame(downloaded, provider, len(providers))
            if one.empty or "Adj Close" not in one.columns:
                failed.append(original)
                Manifest().record(event="prices_ticker", status="missing", ticker=original, provider_ticker=provider)
                continue
            one.index = pd.to_datetime(one.index, errors="coerce")
            one = one.loc[one.index.notna()].sort_index()
            one = one.loc[one["Adj Close"].notna()]
            if one.empty:
                failed.append(original)
                continue
            monthly = one.resample("ME").last()
            last_observation = one.index.to_series().resample("ME").last()
            frame = pd.DataFrame(
                {
                    "date": last_observation,
                    "month_end": monthly.index,
                    "ticker": original,
                    "provider_ticker": provider,
                    "close": pd.to_numeric(monthly.get("Close"), errors="coerce"),
                    "adjusted_close": pd.to_numeric(monthly["Adj Close"], errors="coerce"),
                    "volume": pd.to_numeric(monthly.get("Volume"), errors="coerce"),
                }
            ).reset_index(drop=True)
            current_period = pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M")
            frame = frame.loc[frame["month_end"].dt.to_period("M") < current_period].copy()
            frame["return"] = frame["adjusted_close"].pct_change(fill_method=None)
            parts.append(frame)
            Manifest().record(event="prices_ticker", status="ok", ticker=original, rows=len(frame))

    result = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=PRICE_COLUMNS)
    result = result[PRICE_COLUMNS].sort_values(["ticker", "month_end"]).reset_index(drop=True)
    write_dataset(
        result,
        Path("processed") / output_name,
        source="Yahoo Finance via yfinance",
        extra_metadata={
            "retrieved_at_utc": utc_now(), "start": start, "end": end,
            "requested_tickers": canonical, "failed_tickers": failed,
            "adjustment": "Adj Close: dividendos e desdobramentos; retorno calculado sobre adjusted_close",
        },
    )
    return result, failed
