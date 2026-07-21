from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from .core import write_dataset
from .http import CachedHttpClient


FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def _completed_months(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    current_period = pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M")
    return frame.loc[frame[date_column].dt.to_period("M") < current_period].copy()


def collect_fred_series(
    series_id: str,
    *,
    refresh: bool = False,
    client: CachedHttpClient | None = None,
) -> pd.DataFrame:
    client = client or CachedHttpClient()
    key = f"fred/{series_id}.csv"
    result = client.get(FRED_CSV.format(series_id=series_id), key, refresh=refresh)
    raw = pd.read_csv(BytesIO(result.content))
    if raw.shape[1] < 2:
        raise ValueError(f"resposta FRED sem coluna de valores para {series_id}")
    raw.columns = ["date", "value", *list(raw.columns[2:])]
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw.dropna(subset=["date"]).sort_values("date")
    monthly = raw.set_index("date")["value"].resample("ME").last().rename("value").reset_index()
    monthly = _completed_months(monthly)
    monthly.insert(1, "series_id", series_id)
    monthly["frequency"] = "monthly_last_observation"
    write_dataset(
        monthly,
        Path("processed") / f"fred_{series_id}_mensal.csv",
        source=f"Federal Reserve Bank of St. Louis (FRED), serie {series_id}",
        extra_metadata={"cache_hit": result.cache_hit, "raw_cache": str(result.path)},
    )
    return monthly


def ingest_macro_file(
    path: str | Path,
    *,
    series_id: str,
    date_column: str | None = None,
    value_column: str | None = None,
    source_label: str = "arquivo fornecido pela equipe",
) -> pd.DataFrame:
    """Normaliza CSV exportado de fonte licenciada, inclusive TradingView."""
    source_path = Path(path).resolve()
    raw = pd.read_csv(source_path, sep=None, engine="python")
    names = {str(column).strip().lower(): column for column in raw.columns}
    date_column = date_column or next((names[name] for name in ("date", "observation_date", "time", "datetime") if name in names), None)
    value_column = value_column or next((names[name] for name in (series_id.lower(), "close", "value") if name in names), None)
    if date_column not in raw.columns or value_column not in raw.columns:
        raise ValueError(f"colunas de data/valor nao identificadas; colunas={list(raw.columns)}")
    date_values = raw[date_column]
    if pd.api.types.is_numeric_dtype(date_values):
        median = pd.to_numeric(date_values, errors="coerce").dropna().median()
        unit = "ms" if median > 10_000_000_000 else "s"
        dates = pd.to_datetime(date_values, unit=unit, errors="coerce", utc=True).dt.tz_convert(None)
    else:
        dates = pd.to_datetime(date_values, errors="coerce", utc=True).dt.tz_convert(None)
    normalized = pd.DataFrame({"date": dates, "value": pd.to_numeric(raw[value_column], errors="coerce")})
    normalized = normalized.dropna(subset=["date"]).sort_values("date")
    monthly = normalized.set_index("date")["value"].resample("ME").last().rename("value").reset_index()
    monthly = _completed_months(monthly)
    monthly.insert(1, "series_id", series_id)
    monthly["frequency"] = "monthly_last_observation"
    write_dataset(
        monthly,
        Path("processed") / f"fred_{series_id}_mensal.csv",
        source=source_label,
        extra_metadata={
            "input_file": str(source_path), "date_column": str(date_column), "value_column": str(value_column),
            "note": "Arquivo externo normalizado; confirmar permissao de uso/exportacao e preservar o original.",
        },
    )
    return monthly
