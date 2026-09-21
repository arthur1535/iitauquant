"""Pesquisa determinística em arquivos locais; nunca envia ordens ou baixa dados.

``run_research`` devolve um relatório JSON-safe. ``status == 'blocked'`` é uma
falha de cobertura/qualidade: nenhum grid foi executado. O chamador deve tratar
esse status como falha (por exemplo, exit code 2). Os relatórios são diagnósticos;
nem os melhores parâmetros nem seus resultados são promovidos para negociação.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.engine import ExecutionConfig, run_backtest
from backtest.grid_search import GridSearchConfig, GridSearchRunner
from backtest.stress import DEFAULT_STRESS_SCENARIOS
from backtest.universe import UniverseManifest, load_local_universe, load_universe_manifest
from backtest.validation import chronological_split, walk_forward_validate
from strategies.momentum_atr import MomentumATRConfig


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    """Grade pequena e limites explícitos para execução local previsível."""

    momentum_windows: tuple[int, ...] = (10, 20, 40)
    stop_multipliers: tuple[float, ...] = (2.0, 3.0)
    atr_windows: tuple[int, ...] = (14,)
    train_fraction: float = 0.70
    cost_per_side: float = 0.0015
    minimum_bars: int = 160
    purge_bars: int = 14
    embargo_bars: int = 5
    seed: int = 42  # Não há sorteio; registrado para futuros experimentos opcionais.
    optuna_enabled: bool = False


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, contents: str) -> None:
    """O arquivo final só aparece depois de toda a escrita terminar."""

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _save_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _save_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_text(path, frame.to_csv(index=False))


def _implementation_info() -> dict[str, Any]:
    source = Path(__file__).resolve().parents[1]
    names = (
        "automation/research.py", "backtest/engine.py", "backtest/grid_search.py",
        "backtest/validation.py", "backtest/stress.py", "backtest/universe.py",
        "backtest/statistics.py", "strategies/momentum_atr.py",
    )
    versions: dict[str, str] = {}
    for distribution in ("iitauquant-data", "numpy", "pandas", "pyarrow"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not_installed"
    return {
        "python": platform.python_version(),
        "packages": versions,
        "source_sha256": {name: _sha256(source / name) for name in names},
    }


def run_research(
    manifest_path: Path,
    output_dir: Path,
    *,
    workers: int = 1,
    max_assets: int | None = None,
) -> dict[str, Any]:
    """Pesquisa todos os ativos declarados, com holdout 70/30 e WFA no IS.

    Valida a presença e integridade de TODOS os ativos do manifesto antes de
    aplicar ``max_assets`` (limite de CPU explícito, por ticker em ordem lexical).
    Não há filtro por retorno, status atual ou sobrevivência. Ativos ausentes,
    inválidos ou com menos de 160 barras bloqueiam o lote completo. Dados de
    teste devem declarar ``data_policy.source = 'synthetic_fixture'``.

    O treino do grid e o walk-forward usam apenas os 70% IS. Os 30% finais são
    avaliados com parâmetros fixos; seu warmup usa exclusivamente barras
    anteriores. O stress OOS também mantém esses parâmetros. Workers aceita
    de 1 a 4 processos; Optuna fica desabilitado neste lote econômico.
    """

    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 4:
        raise ValueError("workers deve ser inteiro entre 1 e 4")
    if max_assets is not None and (
        isinstance(max_assets, bool) or not isinstance(max_assets, int) or max_assets < 1
    ):
        raise ValueError("max_assets deve ser None ou inteiro >= 1")

    config = ResearchConfig()
    source_path = Path(manifest_path).resolve()
    manifest = load_universe_manifest(source_path)
    raw_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    if not manifest.assets:
        raise ValueError("manifesto não contém ativos")
    policy = raw_manifest.get("data_policy", {})
    if not isinstance(policy, dict):
        raise ValueError("data_policy deve ser um objeto")
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    implementation = _implementation_info()
    selected = sorted(manifest.assets)[:max_assets]
    histories: dict[str, pd.DataFrame] = {}
    coverage: list[dict[str, Any]] = []

    # Um universo por ticker permite enumerar todos os erros sem suprimir uma
    # ausência; o carregador canônico mantém strict=True em cada leitura.
    audit_manifest = UniverseManifest(
        source_path=manifest.source_path,
        schema_version=manifest.schema_version,
        as_of=manifest.as_of,
        universes={ticker: (ticker,) for ticker in manifest.assets},
        assets=manifest.assets,
    )
    for ticker, asset in sorted(manifest.assets.items()):
        declared = raw_manifest["assets"][ticker]
        row: dict[str, Any] = {
            "ticker": ticker,
            "asset_status_declared": asset.status,
            "local_file_declared": asset.local_file,
            "valid_from_declared": asset.valid_from,
            "valid_to_declared": asset.valid_to,
            "notes_declared": asset.notes,
            "source_declared": declared.get("source", policy.get("source", "not_declared")),
            "adjustment_declared": declared.get("adjustment", policy.get("adjustment", "not_declared")),
            "provenance_independently_verified": False,
            "selected_for_research": ticker in selected,
            "bars": None,
            "status": "pending",
        }
        try:
            frame = load_local_universe(audit_manifest, ticker, strict=True)[ticker]
            local_file = (source_path.parent / asset.local_file).resolve()
            row.update({
                "local_file": str(local_file),
                "file_sha256": _sha256(local_file),
                "data_fingerprint": hashlib.sha256(
                    pd.util.hash_pandas_object(frame, index=True).to_numpy(dtype="uint64").tobytes()
                ).hexdigest(),
                "bars": len(frame),
                "first_bar": frame.index[0].isoformat(),
                "last_bar": frame.index[-1].isoformat(),
                "status": "available" if len(frame) >= config.minimum_bars else "insufficient_bars",
            })
            histories[ticker] = frame
        except FileNotFoundError as error:
            row.update(status="missing", error=str(error))
        except (ValueError, TypeError, OSError) as error:
            row.update(status="invalid", error=str(error))
        coverage.append(row)

    identity = {
        "manifest_sha256": _sha256(source_path),
        "datasets": {row["ticker"]: row.get("data_fingerprint") for row in coverage},
        "config": asdict(config),
        "workers": workers,
        "max_assets": max_assets,
        "implementation": implementation,
    }
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    available = [row["ticker"] for row in coverage if row["status"] == "available"]
    issues = [row for row in coverage if row["status"] != "available"]
    sources = {str(row["source_declared"]) for row in coverage}
    kind = "synthetic_fixture" if sources == {"synthetic_fixture"} else (
        "mixed_synthetic_and_unverified" if "synthetic_fixture" in sources else "historical_unverified"
    )
    artifacts = {
        "summary": str(destination / "summary.json"),
        "coverage_json": str(destination / "coverage.json"),
        "coverage_csv": str(destination / "coverage.csv"),
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "blocked" if issues else "completed",
        "reason": "incomplete_or_invalid_universe" if issues else None,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "research_only",
        "promotion_allowed": False,
        "network_access": False,
        "broker_connected": False,
        "data_kind": kind,
        "config": {**asdict(config), "workers": workers, "max_assets": max_assets},
        "manifest": {"path": str(source_path), "as_of_declared": manifest.as_of, **identity},
        "coverage": {
            "required_count": len(coverage),
            "available_count": len(available),
            "required_tickers": sorted(manifest.assets),
            "selected_tickers": selected,
            "full_universe_researched": not issues and len(selected) == len(coverage),
            "selection_policy": "all_manifest_assets; optional explicit lexical ticker cap; no performance filter",
            "issues": issues,
            "assets": coverage,
        },
        "artifacts": artifacts,
        "limitations": [
            "Diagnostic research only; no automatic parameter promotion or profitability approval.",
            "Manifest source/adjustment claims are declarations, not independent verification.",
            "OHLC adjustment is unverified. Existing Yahoo raw OHLC must not be described as adjusted.",
            "A current manifest plus distressed assets does not establish a verified point-in-time universe.",
            "Walk-forward is confined to IS; OOS is a fixed holdout, not used for parameter selection.",
            "Purge/embargo are bar gaps with flat boundaries; they do not certify all possible label horizons.",
            "Each interval liquidates at final close for accounting; this is not a momentum fill signal.",
            "Stress varies friction on real input bars, without fabricated crashes or imputed suspensions.",
            "No portfolio capital allocation or correlation model; reports evaluate assets individually.",
            "No Optuna run in this bounded pipeline; exhaustive grid has six candidates per asset.",
            "Nonfinite JSON metrics are null; few/zero trades do not substantiate strategy quality.",
        ],
    }
    _save_json(Path(artifacts["coverage_json"]), report["coverage"])
    _save_csv(Path(artifacts["coverage_csv"]), pd.DataFrame(coverage))
    if issues:
        report["grid_tasks"] = 0
        _save_json(Path(artifacts["summary"]), report)
        return _json_safe(report)

    splits = {ticker: chronological_split(histories[ticker], config.train_fraction) for ticker in selected}
    checkpoint = destination / f"grid_is_{run_id[:16]}.parquet"
    grid = GridSearchRunner(GridSearchConfig(
        momentum_windows=config.momentum_windows,
        stop_multipliers=config.stop_multipliers,
        atr_windows=config.atr_windows,
        cost_per_side=config.cost_per_side,
        workers=workers,
        batch_size=6,
        checkpoint_path=checkpoint,
    )).run({ticker: split.train for ticker, split in splits.items()})
    holdout_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    walk_forward_frames: list[pd.DataFrame] = []
    execution = ExecutionConfig(cost_per_side=config.cost_per_side)
    for ticker in selected:
        frame = histories[ticker]
        split = splits[ticker]
        ranking = grid.loc[grid["ticker"].eq(ticker)].sort_values(
            ["sharpe_ratio", "total_return", "momentum_window", "stop_multiplier", "atr_window"],
            ascending=[False, False, True, True, True], kind="mergesort",
        )
        best = ranking.iloc[0]
        strategy = MomentumATRConfig(
            momentum_window=int(best["momentum_window"]),
            atr_window=int(best["atr_window"]),
            stop_multiplier=float(best["stop_multiplier"]),
        )
        oos = run_backtest(
            frame, strategy, execution,
            trade_start=split.test.index[0], trade_end=split.test.index[-1],
        )
        holdout_rows.append({
            "ticker": ticker,
            "asset_status_declared": manifest.assets[ticker].status,
            **asdict(strategy),
            "is_start": split.train.index[0], "is_end": split.train.index[-1],
            "oos_start": split.test.index[0], "oos_end": split.test.index[-1],
            "is_bars": len(split.train), "oos_bars": len(split.test),
            "is_sharpe": best["sharpe_ratio"], "is_dsr": best["deflated_sharpe_ratio"],
            **{f"oos_{key}": value for key, value in oos.metrics.items()},
        })
        wfa = walk_forward_validate(
            split.train,
            momentum_windows=config.momentum_windows,
            stop_multipliers=config.stop_multipliers,
            atr_windows=config.atr_windows,
            train_size=max(60, len(split.train) // 2),
            test_size=max(20, len(split.train) // 5),
            purge=config.purge_bars,
            embargo=config.embargo_bars,
            execution_config=execution,
        )
        wfa.insert(0, "ticker", ticker)
        wfa.insert(1, "scope", "in_sample_only")
        walk_forward_frames.append(wfa)
        for scenario in DEFAULT_STRESS_SCENARIOS:
            stressed = run_backtest(
                frame, strategy,
                ExecutionConfig(cost_per_side=scenario.cost_per_side, stop_slippage=scenario.stop_slippage),
                trade_start=split.test.index[0], trade_end=split.test.index[-1],
            )
            stress_rows.append({
                "ticker": ticker,
                "asset_status_declared": manifest.assets[ticker].status,
                "scope": "out_of_sample_fixed_parameters",
                **asdict(scenario), **asdict(strategy), **stressed.metrics,
            })

    holdout = pd.DataFrame(holdout_rows)
    wfa_all = pd.concat(walk_forward_frames, ignore_index=True)
    stress = pd.DataFrame(stress_rows)
    for name, table in (("grid_is", grid), ("holdout", holdout), ("walk_forward", wfa_all), ("stress_oos", stress)):
        path = destination / f"{name}.csv"
        _save_csv(path, table)
        artifacts[name] = str(path)
    artifacts["grid_checkpoint"] = str(checkpoint)
    report.update({
        "grid_tasks": len(grid),
        "holdout": holdout.to_dict(orient="records"),
        "walk_forward_fold_count": len(wfa_all),
        "stress_scenario_count": len(DEFAULT_STRESS_SCENARIOS),
        "artifact_sha256": {name: _sha256(Path(path)) for name, path in artifacts.items() if name != "summary"},
    })
    _save_json(Path(artifacts["summary"]), report)
    return _json_safe(report)
