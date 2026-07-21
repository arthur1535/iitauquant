from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .core import Manifest, canonical_ticker, write_dataset
from .http import CachedHttpClient


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Ordem e tags ficam preservadas: diferentes emissores usam tags GAAP distintas.
CONCEPTS: dict[str, list[tuple[str, str]]] = {
    "assets": [("us-gaap", "Assets")],
    "equity": [
        ("us-gaap", "StockholdersEquity"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    ],
    "gross_profit": [("us-gaap", "GrossProfit")],
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
    ],
    "shares_outstanding": [
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
    ],
}


def _sec_user_agent(explicit: str | None = None) -> str:
    value = explicit or os.environ.get("SEC_USER_AGENT", "")
    if "@" not in value or len(value) < 8:
        raise ValueError("Informe --sec-user-agent 'Nome email@dominio' ou a variavel SEC_USER_AGENT para cumprir a politica da SEC")
    return value


def collect_sec_ticker_map(
    *, refresh: bool = False, client: CachedHttpClient | None = None,
) -> pd.DataFrame:
    client = client or CachedHttpClient()
    download = client.get(SEC_TICKERS_URL, "sec/company_tickers.json", refresh=refresh)
    payload = json.loads(download.content)
    rows = []
    for item in payload.values():
        rows.append(
            {
                "ticker": canonical_ticker(item["ticker"]),
                "cik": str(item["cik_str"]).zfill(10),
                "company": item["title"],
            }
        )
    return pd.DataFrame(rows).drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True)


def _extract_companyfacts(payload: dict[str, Any], ticker: str, forms: set[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    facts = payload.get("facts", {})
    for metric, tags in CONCEPTS.items():
        for priority, (taxonomy, tag) in enumerate(tags):
            concept = facts.get(taxonomy, {}).get(tag)
            if not concept:
                continue
            for unit, observations in concept.get("units", {}).items():
                for observation in observations:
                    if observation.get("form") not in forms:
                        continue
                    rows.append(
                        {
                            "ticker": ticker,
                            "cik": payload.get("cik"),
                            "company": payload.get("entityName"),
                            "metric": metric,
                            "taxonomy": taxonomy,
                            "tag": tag,
                            "tag_priority": priority,
                            "unit": unit,
                            "value": observation.get("val"),
                            "period_start": observation.get("start"),
                            "fiscal_period_end": observation.get("end"),
                            "availability_date": observation.get("filed"),
                            "fiscal_year": observation.get("fy"),
                            "fiscal_period": observation.get("fp"),
                            "form": observation.get("form"),
                            "accession": observation.get("accn"),
                            "frame": observation.get("frame"),
                        }
                    )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ("period_start", "fiscal_period_end", "availability_date"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["value", "fiscal_period_end", "availability_date"])
    frame["duration_days"] = (frame["fiscal_period_end"] - frame["period_start"]).dt.days
    duration_metrics = frame["metric"].isin({"gross_profit", "revenue"})
    annual_duration = frame["duration_days"].between(270, 430, inclusive="both")
    frame = frame.loc[~duration_metrics | annual_duration].copy()
    return frame.sort_values(["metric", "fiscal_period_end", "availability_date", "tag_priority"])


def collect_sec_fundamentals(
    tickers: Iterable[str],
    *,
    forms: Iterable[str] = ("10-K", "10-K/A"),
    refresh: bool = False,
    user_agent: str | None = None,
    pause_seconds: float = 0.15,
) -> tuple[pd.DataFrame, list[str]]:
    agent = _sec_user_agent(user_agent)
    client = CachedHttpClient(user_agent=agent)
    mapping = collect_sec_ticker_map(refresh=refresh, client=client).set_index("ticker")
    requested = list(dict.fromkeys(canonical_ticker(item) for item in tickers))
    parts: list[pd.DataFrame] = []
    failed: list[str] = []
    for ticker in requested:
        lookup = ticker.replace("-", ".") if ticker not in mapping.index and ticker.replace("-", ".") in mapping.index else ticker
        if lookup not in mapping.index:
            failed.append(ticker)
            Manifest().record(event="sec_companyfacts", status="ticker_not_found", ticker=ticker)
            continue
        cik = mapping.loc[lookup, "cik"]
        try:
            download = client.get(
                SEC_COMPANYFACTS_URL.format(cik=cik),
                f"sec/companyfacts/CIK{cik}.json",
                refresh=refresh,
                pause_seconds=max(pause_seconds, 0.1),
            )
            extracted = _extract_companyfacts(json.loads(download.content), ticker, set(forms))
            if extracted.empty:
                failed.append(ticker)
            else:
                parts.append(extracted)
            Manifest().record(event="sec_companyfacts", status="ok", ticker=ticker, cik=cik, rows=len(extracted), cache_hit=download.cache_hit)
        except Exception as exc:
            failed.append(ticker)
            Manifest().record(event="sec_companyfacts", status="failed", ticker=ticker, cik=cik, error=str(exc))
        time.sleep(pause_seconds)
    result = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    write_dataset(
        result,
        Path("processed") / "fundamentos_sec_anuais.csv",
        source="SEC EDGAR Company Facts API",
        extra_metadata={
            "requested_tickers": requested, "failed_tickers": failed, "forms": list(forms),
            "point_in_time_field": "availability_date (SEC filed)",
            "warning": "Escolher fatos com availability_date <= data da decisao; revisoes posteriores nao podem retroagir.",
        },
    )
    return result, failed
