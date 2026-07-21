from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from .core import write_dataset
from .http import CachedHttpClient


FF5_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"


def _read_zip_text(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith((".csv", ".txt"))]
        if not names:
            raise ValueError("ZIP da biblioteca Kenneth French nao contem CSV/TXT")
        raw = archive.read(names[0])
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("nao foi possivel decodificar arquivo Kenneth French")


def parse_monthly_french(text: str) -> pd.DataFrame:
    """Extrai apenas o primeiro bloco mensal YYYYMM e converte percentuais em decimais."""
    rows = list(csv.reader(StringIO(text)))
    header_index = next(
        (idx for idx, row in enumerate(rows) if row and any("Mkt-RF" in cell or cell.strip() == "Mom" for cell in row)),
        None,
    )
    if header_index is None:
        raise ValueError("cabecalho mensal nao encontrado no arquivo Kenneth French")
    header = [cell.strip() or "date" for cell in rows[header_index]]
    header[0] = "date"
    values: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        if not row:
            if values:
                break
            continue
        date_token = row[0].strip()
        if len(date_token) == 6 and date_token.isdigit():
            values.append(row[: len(header)])
        elif values:
            break
    if not values:
        raise ValueError("bloco de observacoes mensais vazio")
    frame = pd.DataFrame(values, columns=header)
    frame["date"] = pd.to_datetime(frame["date"].str.strip(), format="%Y%m") + pd.offsets.MonthEnd(0)
    for column in frame.columns.drop("date"):
        frame[column] = pd.to_numeric(frame[column].astype(str).str.strip(), errors="coerce")
        frame[column] = frame[column].replace({-99.99: pd.NA, -999.0: pd.NA}) / 100.0
    return frame


def collect_fama_french(*, refresh: bool = False, client: CachedHttpClient | None = None) -> pd.DataFrame:
    client = client or CachedHttpClient()
    ff5_download = client.get(FF5_URL, "fama_french/ff5_monthly.zip", refresh=refresh)
    mom_download = client.get(MOM_URL, "fama_french/momentum_monthly.zip", refresh=refresh)
    ff5 = parse_monthly_french(_read_zip_text(ff5_download.content))
    momentum = parse_monthly_french(_read_zip_text(mom_download.content))
    mom_columns = [column for column in momentum.columns if column != "date"]
    if len(mom_columns) != 1:
        raise ValueError(f"arquivo de momentum inesperado: {mom_columns}")
    momentum = momentum.rename(columns={mom_columns[0]: "MOM"})
    merged = ff5.merge(momentum[["date", "MOM"]], on="date", how="inner", validate="one_to_one")
    merged = merged.dropna(subset=["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "MOM"])
    merged = merged.sort_values("date").reset_index(drop=True)
    write_dataset(
        merged,
        Path("processed") / "fama_french_5_mais_momentum_mensal.csv",
        source="Kenneth R. French Data Library",
        extra_metadata={
            "units": "decimal returns", "missing_codes_replaced": [-99.99, -999],
            "ff5_cache_hit": ff5_download.cache_hit, "momentum_cache_hit": mom_download.cache_hit,
        },
    )
    return merged
