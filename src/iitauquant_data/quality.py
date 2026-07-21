from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .core import DATA_ROOT, REPORT_ROOT, atomic_write_text, ensure_directories, utc_now, write_dataset


@dataclass
class Issue:
    dataset: str
    severity: str
    code: str
    detail: str
    ticker: str | None = None
    period: str | None = None


def infer_frequency(dates: pd.Series | pd.DatetimeIndex) -> str:
    index = pd.DatetimeIndex(pd.to_datetime(dates, errors="coerce")).dropna().sort_values().unique()
    if len(index) < 3:
        return "insufficient"
    median_days = float(np.median(np.diff(index.values).astype("timedelta64[D]").astype(float)))
    if median_days <= 2:
        return "daily"
    if median_days <= 10:
        return "weekly"
    if median_days <= 40:
        return "monthly"
    if median_days <= 100:
        return "quarterly"
    if median_days <= 400:
        return "annual"
    return "irregular"


def audit_prices(
    frame: pd.DataFrame, *, max_missing_fraction: float = 0.05,
    max_return_abs: float = 0.80, max_staleness_days: int = 45,
) -> list[Issue]:
    issues: list[Issue] = []
    required = {"month_end", "ticker", "adjusted_close", "return"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        return [Issue("prices", "error", "missing_columns", f"Colunas ausentes: {sorted(missing_columns)}")]
    data = frame.copy()
    data["month_end"] = pd.to_datetime(data["month_end"], errors="coerce")
    duplicates = data.duplicated(["ticker", "month_end"], keep=False)
    if duplicates.any():
        issues.append(Issue("prices", "error", "duplicate_key", f"{int(duplicates.sum())} linhas ticker-mes duplicadas"))
    invalid_dates = int(data["month_end"].isna().sum())
    if invalid_dates:
        issues.append(Issue("prices", "error", "invalid_date", f"{invalid_dates} datas invalidas"))
    invalid_prices = data["adjusted_close"].isna() | (pd.to_numeric(data["adjusted_close"], errors="coerce") <= 0)
    if invalid_prices.any():
        issues.append(Issue("prices", "error", "invalid_adjusted_price", f"{int(invalid_prices.sum())} precos ajustados ausentes/nao positivos"))
    for ticker, group in data.dropna(subset=["month_end"]).groupby("ticker"):
        group = group.sort_values("month_end")
        frequency = infer_frequency(group["month_end"])
        if frequency not in {"monthly", "insufficient"}:
            issues.append(Issue("prices", "error", "incompatible_frequency", f"Frequencia inferida: {frequency}", str(ticker)))
        if len(group) >= 2:
            expected = pd.date_range(group["month_end"].min(), group["month_end"].max(), freq="ME")
            observed = pd.DatetimeIndex(group["month_end"].dropna().unique())
            missing = expected.difference(observed)
            fraction = len(missing) / len(expected) if len(expected) else 0.0
            if fraction > max_missing_fraction:
                issues.append(Issue("prices", "warning", "missing_months", f"{len(missing)}/{len(expected)} meses ausentes ({fraction:.1%})", str(ticker)))
        last_date = group["month_end"].max()
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        if pd.notna(last_date) and (today - last_date).days > max_staleness_days:
            issues.append(Issue("prices", "warning", "stale_data", f"Ultimo mes ha {(today - last_date).days} dias", str(ticker), str(last_date.date())))
        extreme = group.loc[pd.to_numeric(group["return"], errors="coerce").abs() > max_return_abs, "month_end"]
        if not extreme.empty:
            issues.append(Issue("prices", "warning", "extreme_return", f"{len(extreme)} retornos com |r| > {max_return_abs:.0%}", str(ticker), str(extreme.iloc[0].date())))
    return issues


def audit_fundamentals(frame: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    required = {"ticker", "metric", "fiscal_year", "fiscal_period_end", "availability_date", "value"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        return [Issue("fundamentals", "error", "missing_columns", f"Colunas ausentes: {sorted(missing_columns)}")]
    data = frame.copy()
    data["fiscal_period_end"] = pd.to_datetime(data["fiscal_period_end"], errors="coerce")
    data["availability_date"] = pd.to_datetime(data["availability_date"], errors="coerce")
    bad_availability = data["availability_date"].isna() | (data["availability_date"] < data["fiscal_period_end"])
    if bad_availability.any():
        issues.append(Issue("fundamentals", "error", "invalid_availability_date", f"{int(bad_availability.sum())} fatos sem data de disponibilidade valida"))
    needed = {"assets", "equity", "gross_profit", "revenue", "shares_outstanding"}
    annual = data.loc[data["fiscal_year"].notna()]
    grouped = annual.groupby(["ticker", "fiscal_year"])["metric"].agg(lambda values: set(values))
    for (ticker, year), present in grouped.items():
        absent = sorted(needed.difference(present))
        if absent:
            issues.append(Issue("fundamentals", "warning", "incomplete_fundamentals", f"Campos ausentes: {absent}", str(ticker), str(int(year))))
    return issues


def audit_monthly_series(frame: pd.DataFrame, dataset: str, date_column: str = "date") -> list[Issue]:
    if date_column not in frame.columns:
        return [Issue(dataset, "error", "missing_date_column", f"Coluna ausente: {date_column}")]
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    issues: list[Issue] = []
    if dates.isna().any():
        issues.append(Issue(dataset, "error", "invalid_date", f"{int(dates.isna().sum())} datas invalidas"))
    frequency = infer_frequency(dates)
    if frequency not in {"monthly", "insufficient"}:
        issues.append(Issue(dataset, "error", "incompatible_frequency", f"Esperada monthly; inferida {frequency}"))
    numeric = frame.select_dtypes(include="number")
    if not numeric.empty and numeric.isna().any().any():
        issues.append(Issue(dataset, "warning", "missing_values", f"{int(numeric.isna().sum().sum())} valores numericos ausentes"))
    return issues


def run_full_audit(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_directories()
    issues: list[Issue] = []
    checked: dict[str, Any] = {}
    prices_path = DATA_ROOT / "processed" / "precos_mensais.csv"
    if prices_path.exists():
        frame = pd.read_csv(prices_path)
        issues.extend(audit_prices(
            frame,
            max_missing_fraction=config["quality"]["max_missing_monthly_fraction"],
            max_return_abs=config["quality"]["max_price_return_abs"],
            max_staleness_days=config["quality"]["max_staleness_days"],
        ))
        metadata_path = prices_path.with_suffix(prices_path.suffix + ".meta.json")
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("failed_tickers"):
                issues.append(Issue("prices", "error", "download_failures", f"Tickers sem download: {metadata['failed_tickers']}"))
        checked["prices"] = {"path": str(prices_path), "rows": len(frame)}
    else:
        issues.append(Issue("prices", "error", "dataset_missing", str(prices_path)))
    fundamental_path = DATA_ROOT / "processed" / "fundamentos_sec_anuais.csv"
    if fundamental_path.exists():
        frame = pd.read_csv(fundamental_path)
        issues.extend(audit_fundamentals(frame))
        checked["fundamentals"] = {"path": str(fundamental_path), "rows": len(frame)}
    else:
        issues.append(Issue("fundamentals", "error", "dataset_missing", str(fundamental_path)))
    for path, name in (
        (DATA_ROOT / "processed" / "fred_BAMLH0A0HYM2_mensal.csv", "fred"),
        (DATA_ROOT / "processed" / "fama_french_5_mais_momentum_mensal.csv", "fama_french"),
    ):
        if path.exists():
            frame = pd.read_csv(path)
            issues.extend(audit_monthly_series(frame, name))
            if name == "fred" and not frame.empty:
                observed_start = pd.to_datetime(frame["date"], errors="coerce").min()
                required_start = pd.Timestamp(config["fred"]["minimum_start"])
                if pd.notna(observed_start) and observed_start > required_start:
                    issues.append(Issue("fred", "error", "insufficient_history", f"Inicio observado {observed_start.date()} posterior ao minimo {required_start.date()}; crises de calibracao nao estao cobertas"))
            checked[name] = {"path": str(path), "rows": len(frame)}
        else:
            issues.append(Issue(name, "error", "dataset_missing", str(path)))
    universe_path = DATA_ROOT / "processed" / "universo_sp500_atual.csv"
    if universe_path.exists():
        universe = pd.read_csv(universe_path)
        checked["sp500_universe"] = {"path": str(universe_path), "rows": len(universe), "point_in_time": False}
        issues.append(Issue("universe", "warning", "survivorship_bias", "Composicao atual do S&P 500; membros removidos historicamente estao ausentes"))
    else:
        issues.append(Issue("universe", "error", "dataset_missing", str(universe_path)))
    holdings_pattern = f"holdings_{config['holdings']['selected_fund'].lower()}_*.csv"
    holding_files = sorted((DATA_ROOT / "processed").glob(holdings_pattern))
    if holding_files:
        latest_holdings = pd.read_csv(holding_files[-1])
        checked["holdings"] = {"path": str(holding_files[-1]), "rows": len(latest_holdings), "point_in_time": False}
        issues.append(Issue("holdings", "warning", "survivorship_bias", "Snapshot atual de holdings nao e composicao historica"))
    else:
        issues.append(Issue("holdings", "warning", "dataset_missing", f"Nenhum arquivo {holdings_pattern}"))
    issue_frame = pd.DataFrame([asdict(item) for item in issues], columns=list(Issue.__annotations__))
    write_dataset(issue_frame, Path("relatorios") / "qualidade_dados.csv", source="auditoria interna")
    summary = {
        "generated_at_utc": utc_now(),
        "status": "FAIL" if any(item.severity == "error" for item in issues) else "PASS_WITH_WARNINGS" if issues else "PASS",
        "counts": {
            "errors": sum(item.severity == "error" for item in issues),
            "warnings": sum(item.severity == "warning" for item in issues),
        },
        "checked": checked,
        "methodological_flags": {
            "survivorship_bias": True,
            "price_source_not_institutional": True,
            "fundamentals_point_in_time_field": "availability_date",
            "tradingview_used_in_backtest": False,
        },
    }
    atomic_write_text(REPORT_ROOT / "resumo_qualidade.json", json.dumps(summary, indent=2, ensure_ascii=False))
    return issue_frame, summary
