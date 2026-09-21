"""Universos point-in-time definidos localmente, inclusive ativos deslistados."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from strategies.momentum_atr import validate_ohlc


@dataclass(frozen=True, slots=True)
class AssetRecord:
    ticker: str
    local_file: str
    status: str
    valid_from: str | None = None
    valid_to: str | None = None
    notes: str | None = None

    def active_on(self, date: str | pd.Timestamp) -> bool:
        timestamp = pd.Timestamp(date)
        return (self.valid_from is None or timestamp >= pd.Timestamp(self.valid_from)) and (
            self.valid_to is None or timestamp <= pd.Timestamp(self.valid_to)
        )


@dataclass(frozen=True, slots=True)
class UniverseManifest:
    source_path: Path
    schema_version: int
    as_of: str
    universes: dict[str, tuple[str, ...]]
    assets: dict[str, AssetRecord]

    def members(self, universe: str, on_date: str | pd.Timestamp | None = None) -> tuple[AssetRecord, ...]:
        if universe not in self.universes:
            raise KeyError(f"universo desconhecido: {universe}")
        records = tuple(self.assets[ticker] for ticker in self.universes[universe])
        if on_date is not None:
            records = tuple(record for record in records if record.active_on(on_date))
        return records


def load_universe_manifest(path: str | Path) -> UniverseManifest:
    """Lê um manifesto versionado; nunca consulta uma lista atual na internet."""

    source = Path(path).resolve()
    with source.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("schema_version do manifesto deve ser 1")
    if not isinstance(payload.get("universes"), dict) or not isinstance(payload.get("assets"), dict):
        raise ValueError("manifesto requer objetos 'universes' e 'assets'")

    assets: dict[str, AssetRecord] = {}
    for ticker, raw in payload["assets"].items():
        if not isinstance(raw, dict) or not raw.get("local_file") or not raw.get("status"):
            raise ValueError(f"registro inválido para {ticker}")
        assets[ticker] = AssetRecord(
            ticker=ticker,
            local_file=str(raw["local_file"]),
            status=str(raw["status"]),
            valid_from=raw.get("valid_from"),
            valid_to=raw.get("valid_to"),
            notes=raw.get("notes"),
        )
    universes = {name: tuple(members) for name, members in payload["universes"].items()}
    unknown = sorted({ticker for members in universes.values() for ticker in members if ticker not in assets})
    if unknown:
        raise ValueError(f"tickers sem metadados no manifesto: {', '.join(unknown)}")
    return UniverseManifest(
        source_path=source,
        schema_version=1,
        as_of=str(payload.get("as_of", "")),
        universes=universes,
        assets=assets,
    )


def _safe_asset_path(manifest: UniverseManifest, asset: AssetRecord, data_root: str | Path | None) -> Path:
    project_root = manifest.source_path.parent.parent.resolve()
    if data_root is None:
        candidate = (manifest.source_path.parent / asset.local_file).resolve()
        allowed_root = project_root
    else:
        allowed_root = Path(data_root).resolve()
        candidate = (allowed_root / Path(asset.local_file).name).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as error:
        raise ValueError(f"local_file sai do diretório permitido: {asset.local_file}") from error
    return candidate


def load_local_history(
    manifest: UniverseManifest,
    asset: AssetRecord,
    *,
    data_root: str | Path | None = None,
) -> pd.DataFrame:
    """Carrega CSV/Parquet local e preserva interrupções do histórico."""

    path = _safe_asset_path(manifest, asset, data_root)
    if not path.exists():
        raise FileNotFoundError(f"histórico local ausente para {asset.ticker}: {path}")
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif suffix == ".csv":
        frame = pd.read_csv(path)
    else:
        raise ValueError(f"formato não suportado para {asset.ticker}: {suffix}")

    frame = frame.rename(columns={column: str(column).strip().lower() for column in frame.columns})
    if not isinstance(frame.index, pd.DatetimeIndex):
        date_column = next((name for name in ("date", "datetime", "timestamp") if name in frame), None)
        if date_column is None:
            raise ValueError(f"{path} precisa de DatetimeIndex ou coluna date/datetime/timestamp")
        frame.index = pd.to_datetime(frame.pop(date_column), errors="raise")
    if asset.valid_from:
        frame = frame.loc[frame.index >= pd.Timestamp(asset.valid_from)]
    if asset.valid_to:
        frame = frame.loc[frame.index <= pd.Timestamp(asset.valid_to)]
    # Deliberadamente sem ffill: uma suspensão não vira retorno zero sintético.
    return validate_ohlc(frame)


def load_local_universe(
    manifest: UniverseManifest,
    universe: str,
    *,
    data_root: str | Path | None = None,
    on_date: str | pd.Timestamp | None = None,
    strict: bool = True,
) -> dict[str, pd.DataFrame]:
    """Carrega todas as séries locais de um universo point-in-time."""

    result: dict[str, pd.DataFrame] = {}
    for asset in manifest.members(universe, on_date=on_date):
        try:
            result[asset.ticker] = load_local_history(manifest, asset, data_root=data_root)
        except FileNotFoundError:
            if strict:
                raise
    return result
