from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from .core import canonical_ticker, write_dataset, yahoo_ticker
from .http import CachedHttpClient


SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def collect_sp500(*, refresh: bool = False, client: CachedHttpClient | None = None) -> pd.DataFrame:
    client = client or CachedHttpClient()
    download = client.get(SP500_URL, "universes/sp500.html", refresh=refresh)
    tables = pd.read_html(StringIO(download.content.decode("utf-8")))
    table = next((item for item in tables if "Symbol" in item.columns and "Security" in item.columns), None)
    if table is None:
        raise ValueError("tabela do S&P 500 nao encontrada")
    result = pd.DataFrame(
        {
            "ticker": table["Symbol"].map(canonical_ticker),
            "provider_ticker": table["Symbol"].map(yahoo_ticker),
            "security": table["Security"].astype(str).str.strip(),
            "sector": table.get("GICS Sector", pd.Series(index=table.index, dtype="object")),
            "sub_industry": table.get("GICS Sub-Industry", pd.Series(index=table.index, dtype="object")),
            "date_added": pd.to_datetime(table.get("Date added"), errors="coerce"),
            "cik": table.get("CIK", pd.Series(index=table.index, dtype="object")).astype(str).str.zfill(10),
        }
    )
    result["universe"] = "S&P 500"
    result["point_in_time"] = False
    result["survivorship_warning"] = "Composicao atual; inadequada para inferencia historica sem declarar vies de sobrevivencia"
    result = result.drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True)
    write_dataset(
        result,
        Path("processed") / "universo_sp500_atual.csv",
        source="Wikipedia (composicao publica atual do S&P 500)",
        extra_metadata={
            "point_in_time": False, "cache_hit": download.cache_hit,
            "warning": "A data de entrada nao reconstrói membros removidos; nao e um universo historico.",
        },
    )
    return result


def _read_holdings(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        attempts: list[Exception] = []
        for skiprows in (0, 1, 2, 9, 10):
            try:
                frame = pd.read_csv(path, skiprows=skiprows, sep=None, engine="python")
                if frame.shape[1] >= 2:
                    return frame
            except Exception as exc:
                attempts.append(exc)
        raise ValueError(f"nao foi possivel ler holdings: {attempts[-1]}")
    raise ValueError(f"formato de holdings nao suportado: {suffix}")


def ingest_holdings(
    path: str | Path,
    *,
    fund: str,
    as_of: str,
    ticker_column: str | None = None,
) -> pd.DataFrame:
    source_path = Path(path).resolve()
    raw = _read_holdings(source_path)
    normalized_names = {str(column).strip().lower(): column for column in raw.columns}
    candidates = ["ticker", "symbol", "holding ticker", "sedol ticker"]
    selected: Any = ticker_column
    if selected is None:
        selected = next((normalized_names[item] for item in candidates if item in normalized_names), None)
    if selected not in raw.columns:
        raise ValueError(f"coluna de ticker nao identificada; colunas={list(raw.columns)}")
    rows: list[dict[str, Any]] = []
    invalid: list[str] = []
    for value in raw[selected]:
        try:
            ticker = canonical_ticker(value)
        except ValueError:
            invalid.append(str(value))
            continue
        rows.append({"fund": fund.upper(), "as_of": pd.Timestamp(as_of), "ticker": ticker, "provider_ticker": yahoo_ticker(ticker)})
    result = pd.DataFrame(rows).drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True)
    result["point_in_time"] = False
    result["survivorship_warning"] = "Snapshot unico de holdings; nao representa composicoes historicas"
    write_dataset(
        result,
        Path("processed") / f"holdings_{fund.lower()}_{pd.Timestamp(as_of):%Y%m%d}.csv",
        source=str(source_path),
        extra_metadata={"fund": fund.upper(), "as_of": as_of, "invalid_rows": invalid, "point_in_time": False},
    )
    return result
