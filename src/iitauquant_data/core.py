from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "dados"
CACHE_ROOT = DATA_ROOT / "cache"
RAW_ROOT = DATA_ROOT / "raw"
PROCESSED_ROOT = DATA_ROOT / "processed"
REPORT_ROOT = DATA_ROOT / "relatorios"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    for path in (CACHE_ROOT, RAW_ROOT, PROCESSED_ROOT, REPORT_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else PROJECT_ROOT / "config" / "dados.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class CacheResult:
    content: bytes
    cache_hit: bool
    path: Path


class Manifest:
    """Registro append-only de cada tentativa de coleta e artefato produzido."""

    def __init__(self, path: Path | None = None) -> None:
        ensure_directories()
        self.path = path or (DATA_ROOT / "manifest.jsonl")

    def record(self, **event: Any) -> None:
        payload = {"timestamp_utc": utc_now(), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def write_dataset(
    frame: pd.DataFrame,
    relative_path: str | Path,
    *,
    source: str,
    extra_metadata: dict[str, Any] | None = None,
) -> Path:
    """Grava CSV e sidecar JSON de modo atomico, com hash e esquema."""
    ensure_directories()
    path = DATA_ROOT / relative_path
    csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    atomic_write_bytes(path, csv_bytes)
    metadata = {
        "source": source,
        "retrieved_at_utc": utc_now(),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "sha256": sha256_bytes(csv_bytes),
        **(extra_metadata or {}),
    }
    atomic_write_text(path.with_suffix(path.suffix + ".meta.json"), json.dumps(metadata, indent=2, ensure_ascii=False))
    Manifest().record(event="dataset_written", path=str(path.relative_to(PROJECT_ROOT)), **metadata)
    return path


_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-/^=]{0,19}$")


def canonical_ticker(value: Any) -> str:
    ticker = str(value).strip().upper()
    ticker = re.sub(r"\s+", "", ticker)
    if not ticker or ticker in {"NAN", "NONE", "N/A", "NA", "-", "--"}:
        raise ValueError("ticker vazio")
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(f"ticker invalido: {value!r}")
    return ticker


def yahoo_ticker(value: Any) -> str:
    """Converte a classe com ponto usada em universos para a sintaxe do Yahoo."""
    return canonical_ticker(value).replace(".", "-")


def normalize_month_end(values: Any) -> pd.DatetimeIndex:
    dates = pd.to_datetime(values, errors="coerce", utc=True)
    if bool(pd.isna(dates).any()):
        raise ValueError("ha datas invalidas")
    naive = dates.tz_convert(None) if isinstance(dates, pd.DatetimeIndex) else dates.dt.tz_convert(None)
    return pd.DatetimeIndex(naive).to_period("M").to_timestamp("M")
