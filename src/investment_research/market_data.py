"""Snapshots isolados com preços ajustados, corte de sessão e integridade."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from strategies.momentum_atr import validate_ohlc


def completed_session_cutoff(as_of: str, now: datetime | None = None) -> pd.Timestamp:
    """Exclui o dia corrente até 17h NY, inclusive em dias de fechamento cedo.

    Uma hora de margem evita baixar a barra diária ainda em formação. Feriados
    são tratados pela ausência de barras do fornecedor, não inventados aqui.
    """
    instant = now or datetime.now(timezone.utc)
    local = instant.astimezone(ZoneInfo("America/New_York"))
    last = local.date() if local.hour >= 17 else local.date() - timedelta(days=1)
    return min(pd.Timestamp(as_of).normalize(), pd.Timestamp(last))


def normalize_download(raw: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.copy()
        raw.columns = raw.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    if raw.empty or any(col not in raw for col in required):
        raise ValueError("fornecedor não retornou OHLC, Adj Close e Volume completos")
    frame = raw[required].copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.loc[frame.index <= cutoff].sort_index()
    # Ausências não são preenchidas nem removidas silenciosamente.
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("histórico contém valores ausentes/não finitos")
    ratio = numeric["Adj Close"] / numeric["Close"]
    if (ratio <= 0).any():
        raise ValueError("fator de ajuste inválido")
    result = pd.DataFrame(index=frame.index)
    for col in ["Open", "High", "Low", "Close"]:
        result[col.lower()] = numeric[col] * ratio
    result["raw_close"] = numeric["Close"]
    result["adjustment_factor"] = ratio
    result["volume"] = numeric["Volume"]
    result.index.name = "date"
    return validate_history(result)


def validate_history(frame: pd.DataFrame) -> pd.DataFrame:
    result = validate_ohlc(frame)
    for col in ["raw_close", "volume", "adjustment_factor"]:
        if col not in result or not np.isfinite(result[col].to_numpy(dtype=float)).all():
            raise ValueError(f"campo ausente ou inválido: {col}")
    if (result["volume"] < 0).any() or (result["raw_close"] <= 0).any() or (result["adjustment_factor"] <= 0).any():
        raise ValueError("volume/preço/fator inválido")
    if not np.allclose(result["close"], result["raw_close"] * result["adjustment_factor"], rtol=1e-9, atol=1e-9):
        raise ValueError("escala de ajuste inconsistente com raw_close")
    return result


def snapshot_data(config: dict, directory: Path, as_of: str, *, refresh: bool = False,
                  offline: bool = False) -> tuple[dict[str, pd.DataFrame], list[dict], list[dict]]:
    """Cache só é aceito com sidecar e SHA256; falha nunca vira série sintética."""
    if refresh and offline:
        raise ValueError("--refresh e --offline são incompatíveis")
    directory.mkdir(parents=True, exist_ok=True)
    cutoff = completed_session_cutoff(as_of)
    frames, sources, exclusions = {}, [], []
    for asset in config["assets"]:
        ticker = asset["ticker"]
        path, meta_path = directory / f"{ticker}.csv", directory / f"{ticker}.meta.json"
        try:
            if refresh or not path.exists() or not meta_path.exists():
                if offline:
                    raise ValueError("snapshot auditável ausente; execute --refresh com acesso à rede")
                import yfinance as yf
                raw = yf.download(ticker, start=config["start"], end=(cutoff + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                  auto_adjust=False, actions=False, threads=False, progress=False, timeout=20)
                frame = normalize_download(raw, cutoff)
                content = frame.to_csv(float_format="%.12g").encode("utf-8")
                metadata = {"ticker": ticker, "currency": "USD", "source": "Yahoo Finance via yfinance",
                            "url": f"https://finance.yahoo.com/quote/{ticker}/history/",
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "requested_start": config["start"], "cutoff": str(cutoff.date()),
                            "adjustment": "OHLC * Adj Close / Close; volume original; liquidez usa raw_close",
                            "first_date": str(frame.index.min().date()), "last_date": str(frame.index.max().date()),
                            "rows": len(frame), "sha256": hashlib.sha256(content).hexdigest()}
                # O download inteiro é validado antes de substituir o cache.
                path.write_bytes(content)
                meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            if metadata["ticker"] != ticker or metadata["currency"] != "USD":
                raise ValueError("identidade/moeda do snapshot não corresponde ao universo")
            if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
                raise ValueError("SHA256 não corresponde ao manifesto do snapshot")
            if pd.Timestamp(metadata["requested_start"]) > pd.Timestamp(config["start"]):
                raise ValueError("cache não cobre o início solicitado; execute --refresh")
            frame = pd.read_csv(path, index_col="date", parse_dates=True)
            frame = validate_history(frame.loc[(frame.index <= cutoff) & (frame.index >= pd.Timestamp(config["start"]))])
            metadata = dict(metadata, analysis_first_date=str(frame.index.min().date()),
                            analysis_last_date=str(frame.index.max().date()), analysis_rows=len(frame))
            frames[ticker] = frame
            sources.append(metadata)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            exclusions.append({"ticker": ticker, "reason": str(exc)})
    return frames, sources, exclusions
