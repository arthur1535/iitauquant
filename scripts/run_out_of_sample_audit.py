"""Script de auditoria causal Out-of-Sample (OOS) com contratos temporais estritos.

Tarefa 1: Manifesto temporal, auditoria de datas e separação de contratos
em modo dry-run sem execução de otimização/backtest nesta etapa.
Especificado em docs/AUDITORIA_OOS_TAREFA1.md.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.validation import purged_walk_forward_splits
from strategies.momentum_atr import validate_ohlc

DATA_DIR = ROOT / "data" / "market"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "oos_audit" / "task1_spy"
SPEC_PATH = ROOT / "docs" / "AUDITORIA_OOS_TAREFA1.md"


def _atomic_write(path: Path, content: str) -> None:
    """Escreve um arquivo de forma atômica."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    """Calcula o SHA-256 de um arquivo."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataframe_fingerprint(df: pd.DataFrame) -> str:
    """Calcula o fingerprint de integridade de um DataFrame Pandas."""
    return hashlib.sha256(
        pd.util.hash_pandas_object(df, index=True).to_numpy(dtype="uint64").tobytes()
    ).hexdigest()


def _get_git_info() -> dict[str, Any]:
    """Obtém SHA do commit atual e status dirty do Git de forma segura."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        ).strip()
        status_output = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        ).strip()
        return {"commit_sha": commit, "is_dirty": len(status_output) > 0}
    except Exception:
        return {"commit_sha": "unknown_or_no_git", "is_dirty": True}


def _get_environment_info() -> dict[str, Any]:
    """Obtém versões do Python, plataforma e pacotes essenciais."""
    packages: dict[str, str] = {}
    for pkg in ("numpy", "pandas", "pyarrow", "fastapi"):
        try:
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            packages[pkg] = "not_installed"
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "git": _get_git_info(),
    }


def _get_source_hashes() -> dict[str, str]:
    """Calcula hashes das fontes de implementação críticas."""
    files = {
        "run_out_of_sample_audit.py": ROOT / "scripts" / "run_out_of_sample_audit.py",
        "validation.py": ROOT / "src" / "backtest" / "validation.py",
        "momentum_atr.py": ROOT / "src" / "strategies" / "momentum_atr.py",
    }
    hashes: dict[str, str] = {}
    for name, p in files.items():
        if p.exists():
            hashes[name] = _sha256_file(p)
        else:
            hashes[name] = "missing"
    return hashes


def date_based_split(
    data: pd.DataFrame,
    is_end_date: str = "2022-12-31",
    oos_start_date: str = "2023-01-01",
    as_of: str | None = "2026-09-21",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide a série estritamente por datas de calendário, garantindo ausência de sobreposição.
    
    Aplica o filtro as_of se fornecido.
    """
    frame = validate_ohlc(data)
    if as_of:
        frame = frame.loc[:as_of].copy()

    is_part = frame.loc[:is_end_date].copy()
    oos_part = frame.loc[oos_start_date:].copy()
    if is_part.empty:
        raise ValueError(f"Partição In-Sample vazia para data de corte {is_end_date}")
    if oos_part.empty:
        raise ValueError(f"Partição Out-of-Sample vazia a partir de {oos_start_date}")
    if is_part.index[-1] >= oos_part.index[0]:
        raise ValueError(
            f"Violação temporal: fim do IS ({is_part.index[-1]}) >= início do OOS ({oos_part.index[0]})"
        )
    return is_part, oos_part


@dataclass(frozen=True, slots=True)
class TemporalAuditConfig:
    symbols: tuple[str, ...] = ("SPY",)
    is_end: str = "2022-12-31"
    oos_start: str = "2023-01-01"
    as_of: str = "2026-09-21"
    train_bars: int = 504
    test_bars: int = 63
    purge_bars: int = 1
    embargo_bars: int = 5
    dry_run: bool = True
    output_dir: str = str(DEFAULT_OUTPUT_DIR)


def plan_out_of_sample_audit(config: TemporalAuditConfig) -> dict[str, Any]:
    """Executa o planejamento causal out-of-sample em modo dry-run com geração de evidências determinísticas.
    
    Não executa nenhum backtest, otimização, cálculo de métricas de retorno ou chamada externa.
    """
    env_info = _get_environment_info()
    source_hashes = _get_source_hashes()
    spec_hash = _sha256_file(SPEC_PATH) if SPEC_PATH.exists() else "missing"

    coverage_rows: list[dict[str, Any]] = []
    folds_rows: list[dict[str, Any]] = []
    data_fingerprints: dict[str, str] = {}
    file_hashes: dict[str, str] = {}
    datasets_is: dict[str, pd.DataFrame] = {}
    datasets_oos: dict[str, pd.DataFrame] = {}

    issues: list[dict[str, Any]] = []

    for symbol in config.symbols:
        row: dict[str, Any] = {
            "symbol": symbol,
            "status": "pending",
            "nominal_is_start": "2020-01-01",
            "nominal_is_end": config.is_end,
            "nominal_oos_start": config.oos_start,
            "nominal_oos_end": config.as_of,
            "effective_is_start": None,
            "effective_is_end": None,
            "effective_is_bars": 0,
            "effective_oos_start": None,
            "effective_oos_end": None,
            "effective_oos_bars": 0,
            "total_bars": 0,
            "source_declared": "Yahoo Finance via yfinance (unverified)",
            "adjustments_declared": "Raw OHLC; auto_adjust=False; unverified total return",
            "provenance_independently_verified": False,
            "calendar": "US_EQUITIES" if not symbol.endswith(".SA") else "B3",
            "currency": "USD" if not symbol.endswith(".SA") else "BRL",
            "file_sha256": None,
            "data_fingerprint": None,
            "error": None,
        }

        parquet_path = DATA_DIR / f"{symbol}.parquet"
        if not parquet_path.exists():
            row["status"] = "missing"
            row["error"] = f"Arquivo não encontrado: {parquet_path}"
            issues.append({"symbol": symbol, "error": row["error"]})
            coverage_rows.append(row)
            continue

        try:
            file_hash = _sha256_file(parquet_path)
            file_hashes[symbol] = file_hash
            row["file_sha256"] = file_hash

            raw_df = pd.read_parquet(parquet_path)
            # Validar e cortar em as_of
            validated_df = validate_ohlc(raw_df)
            if config.as_of:
                validated_df = validated_df.loc[:config.as_of].copy()

            data_fp = _dataframe_fingerprint(validated_df)
            data_fingerprints[symbol] = data_fp
            row["data_fingerprint"] = data_fp
            row["total_bars"] = len(validated_df)

            # Verificar se tem histórico total mínimo
            min_required = config.train_bars + config.purge_bars + 1
            if len(validated_df) < min_required:
                row["status"] = "insufficient_bars"
                row["error"] = (
                    f"insufficient_bars: histórico total ({len(validated_df)} barras) menor que o mínimo ({min_required} barras)"
                )
                issues.append({"symbol": symbol, "error": row["error"]})
                coverage_rows.append(row)
                continue

            # Split estrito por datas
            is_df, oos_df = date_based_split(
                validated_df,
                is_end_date=config.is_end,
                oos_start_date=config.oos_start,
                as_of=config.as_of,
            )

            # Verificar se tem histórico suficiente para ao menos 1 fold IS
            if len(is_df) < min_required:
                row["status"] = "insufficient_bars"
                row["error"] = (
                    f"insufficient_bars: histórico IS ({len(is_df)} barras) menor que o mínimo ({min_required} barras)"
                )
                issues.append({"symbol": symbol, "error": row["error"]})
                coverage_rows.append(row)
                continue

            row["status"] = "available"
            row["effective_is_start"] = str(is_df.index[0].date())
            row["effective_is_end"] = str(is_df.index[-1].date())
            row["effective_is_bars"] = len(is_df)
            row["effective_oos_start"] = str(oos_df.index[0].date())
            row["effective_oos_end"] = str(oos_df.index[-1].date())
            row["effective_oos_bars"] = len(oos_df)
            coverage_rows.append(row)

            datasets_is[symbol] = is_df
            datasets_oos[symbol] = oos_df

            # Construção dos folds exclusivamente no IS
            is_folds = purged_walk_forward_splits(
                len(is_df),
                train_size=config.train_bars,
                test_size=config.test_bars,
                purge=config.purge_bars,
                embargo=config.embargo_bars,
                expanding=True,
            )

            for fold in is_folds:
                train_start = is_df.index[fold.train_indices[0]]
                train_end = is_df.index[fold.train_indices[-1]]
                test_start = is_df.index[fold.test_indices[0]]
                test_end = is_df.index[fold.test_indices[-1]]

                purge_start = is_df.index[fold.purge_indices[0]] if len(fold.purge_indices) > 0 else None
                purge_end = is_df.index[fold.purge_indices[-1]] if len(fold.purge_indices) > 0 else None
                embargo_start = is_df.index[fold.embargo_indices[0]] if len(fold.embargo_indices) > 0 else None
                embargo_end = is_df.index[fold.embargo_indices[-1]] if len(fold.embargo_indices) > 0 else None

                is_complete = len(fold.test_indices) == config.test_bars
                notes = "complete_fold" if is_complete else "incomplete_last_fold"

                folds_rows.append({
                    "partition_type": "is_walk_forward",
                    "symbol": symbol,
                    "fold": fold.fold,
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "train_bars": len(fold.train_indices),
                    "purge_start": str(purge_start.date()) if purge_start is not None else "",
                    "purge_end": str(purge_end.date()) if purge_end is not None else "",
                    "purge_bars": len(fold.purge_indices),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    "test_bars": len(fold.test_indices),
                    "embargo_start": str(embargo_start.date()) if embargo_start is not None else "",
                    "embargo_end": str(embargo_end.date()) if embargo_end is not None else "",
                    "embargo_bars": len(fold.embargo_indices),
                    "is_complete": is_complete,
                    "notes": notes,
                })

            # Reserva de Avaliação OOS isolada
            folds_rows.append({
                "partition_type": "oos_evaluation_reserve",
                "symbol": symbol,
                "fold": "reserve",
                "train_start": "",
                "train_end": "",
                "train_bars": 0,
                "purge_start": "",
                "purge_end": "",
                "purge_bars": 0,
                "test_start": str(oos_df.index[0].date()),
                "test_end": str(oos_df.index[-1].date()),
                "test_bars": len(oos_df),
                "embargo_start": "",
                "embargo_end": "",
                "embargo_bars": 0,
                "is_complete": True,
                "notes": "frozen_parameter_evaluation_reserve",
            })

        except Exception as err:
            row["status"] = "invalid"
            row["error"] = str(err)
            issues.append({"symbol": symbol, "error": str(err)})
            coverage_rows.append(row)

    # Identidade determinística do run_id (sem timestamps voláteis)
    identity_payload = {
        "config": {
            "symbols": list(config.symbols),
            "is_end": config.is_end,
            "oos_start": config.oos_start,
            "as_of": config.as_of,
            "train_bars": config.train_bars,
            "test_bars": config.test_bars,
            "purge_bars": config.purge_bars,
            "embargo_bars": config.embargo_bars,
            "dry_run": config.dry_run,
        },
        "file_hashes": file_hashes,
        "data_fingerprints": data_fingerprints,
        "source_hashes": source_hashes,
        "specification_sha256": spec_hash,
        "environment": {
            "python_version": env_info["python_version"],
            "packages": env_info["packages"],
            "git_commit": env_info["git"]["commit_sha"],
        },
    }
    run_id = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    status = "blocked" if issues else "planned"
    reason = "incomplete_or_invalid_symbols" if issues else None

    dest_dir = Path(config.output_dir) / run_id
    manifest_path = dest_dir / "manifest.json"
    coverage_path = dest_dir / "coverage.csv"
    folds_path = dest_dir / "folds.csv"

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "reason": reason,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run_planning",
        "dry_run": config.dry_run,
        "classification": "retrospective_pseudo_oos",
        "governance": {
            "shadow_mode": True,
            "aprovado": False,
            "promotion_allowed": False,
            "network_access": False,
            "broker_connected": False,
            "rationale": (
                "Dados de 2023 a 2026 já integraram a pesquisa exploratória prévia em Global Leaders. "
                "Classificado estritamente como pseudo-OOS retrospectivo; não substitui holdout cego de produção."
            ),
        },
        "target_command": (
            f".\\.venv\\Scripts\\python.exe scripts/run_out_of_sample_audit.py --dry-run "
            f"--symbols {' '.join(config.symbols)} --is-end {config.is_end} --oos-start {config.oos_start} "
            f"--as-of {config.as_of} --train-bars {config.train_bars} --test-bars {config.test_bars} "
            f"--purge-bars {config.purge_bars} --embargo-bars {config.embargo_bars} "
            f"--output-dir {config.output_dir}"
        ),
        "inputs": asdict(config),
        "purging_and_embargo": {
            "purging_status": "gap_only_not_event_purged",
            "purge_bars": config.purge_bars,
            "embargo_bars": config.embargo_bars,
            "notes": (
                "1 bar de purge e 5 barras de embargo são convenções estruturais para teste do planejador, "
                "não limites econometricamente provados. O splitter utiliza gaps planos e não recebe "
                "intervalos de eventos/trades. A reserva OOS permanece intocada."
            ),
        },
        "warmup_and_execution_policy": {
            "warmup": "Barras anteriores podem aquecer indicadores sem contabilizar P&L.",
            "execution": "Execução causal estritamente no open de t+1.",
            "positions": "Cada partição inicia sem posição (zerada) e liquida ao final com custos teóricos.",
            "assumed_cost_per_side": 0.0015,
        },
        "metrics": {
            "dsr": None,
            "pbo": None,
            "sharpe_is": None,
            "sharpe_oos": None,
            "reason": "not_computed_in_dry_run",
        },
        "identity": identity_payload,
        "artifacts": {
            "manifest_json": str(manifest_path),
            "coverage_csv": str(coverage_path),
            "folds_csv": str(folds_path),
        },
        "summary": {
            "symbols_requested": list(config.symbols),
            "symbols_available": [r["symbol"] for r in coverage_rows if r["status"] == "available"],
            "symbols_issues": issues,
            "total_folds_planned": len([f for f in folds_rows if f["partition_type"] == "is_walk_forward"]),
            "incomplete_folds": len([f for f in folds_rows if f.get("notes") == "incomplete_last_fold"]),
            "oos_reserve_bars": {
                r["symbol"]: r["effective_oos_bars"] for r in coverage_rows if r["status"] == "available"
            },
        },
    }

    # Salvar artefatos
    if coverage_rows:
        coverage_df = pd.DataFrame(coverage_rows)
    else:
        coverage_df = pd.DataFrame(columns=[
            "symbol", "status", "nominal_is_start", "nominal_is_end", "nominal_oos_start",
            "nominal_oos_end", "effective_is_start", "effective_is_end", "effective_is_bars",
            "effective_oos_start", "effective_oos_end", "effective_oos_bars", "total_bars",
            "source_declared", "adjustments_declared", "provenance_independently_verified",
            "calendar", "currency", "file_sha256", "data_fingerprint", "error"
        ])

    if folds_rows:
        folds_df = pd.DataFrame(folds_rows)
    else:
        folds_df = pd.DataFrame(columns=[
            "partition_type", "symbol", "fold", "train_start", "train_end", "train_bars",
            "purge_start", "purge_end", "purge_bars", "test_start", "test_end", "test_bars",
            "embargo_start", "embargo_end", "embargo_bars", "is_complete", "notes"
        ])

    _atomic_write(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    _atomic_write(coverage_path, coverage_df.to_csv(index=False))
    _atomic_write(folds_path, folds_df.to_csv(index=False))

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoria Causal OOS - Tarefa 1: Planejamento Temporal e Manifesto Dry-Run"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["SPY"],
        help="Símbolos para a auditoria (ex: SPY ou SPY NVDA)",
    )
    parser.add_argument(
        "--is-end",
        type=str,
        default="2022-12-31",
        help="Data final nominal do In-Sample (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--oos-start",
        type=str,
        default="2023-01-01",
        help="Data inicial nominal do Out-of-Sample (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default="2026-09-21",
        help="Data de corte máxima para a observação local (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--train-bars",
        type=int,
        default=504,
        help="Tamanho do treino inicial em barras (default 504)",
    )
    parser.add_argument(
        "--test-bars",
        type=int,
        default=63,
        help="Tamanho do teste de cada fold em barras (default 63)",
    )
    parser.add_argument(
        "--purge-bars",
        type=int,
        default=1,
        help="Barras de purga entre treino e teste (default 1)",
    )
    parser.add_argument(
        "--embargo-bars",
        type=int,
        default=5,
        help="Barras de embargo após o teste (default 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Diretório de destino dos artefatos da Tarefa 1",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Apenas gera o contrato temporal e manifesto sem rodar backtests/otimizações",
    )

    args = parser.parse_args()

    # Tratar símbolos se passados como string separada por vírgula
    raw_symbols = args.symbols
    parsed_symbols: list[str] = []
    for item in raw_symbols:
        for s in item.replace(",", " ").split():
            if s.strip():
                parsed_symbols.append(s.strip().upper())

    config = TemporalAuditConfig(
        symbols=tuple(parsed_symbols),
        is_end=args.is_end,
        oos_start=args.oos_start,
        as_of=args.as_of,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        purge_bars=args.purge_bars,
        embargo_bars=args.embargo_bars,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )

    manifest = plan_out_of_sample_audit(config)

    print(f"=== AUDITORIA TEMPORAL OOS (TAREFA 1 - DRY-RUN) ===")
    print(f"Status: {manifest['status']}")
    print(f"Run ID: {manifest['run_id']}")
    print(f"Símbolos: {', '.join(config.symbols)}")
    print(f"Classificação: {manifest['classification']}")
    print(
        f"Governança: shadow_mode={manifest['governance']['shadow_mode']} | "
        f"aprovado={manifest['governance']['aprovado']} | "
        f"promotion_allowed={manifest['governance']['promotion_allowed']}"
    )
    print(f"Purging: {manifest['purging_and_embargo']['purging_status']}")
    print(f"DSR: {manifest['metrics']['dsr']} ({manifest['metrics']['reason']})")
    print(f"PBO: {manifest['metrics']['pbo']} ({manifest['metrics']['reason']})")
    print(f"Artefatos salvos em:")
    for k, p in manifest["artifacts"].items():
        print(f"  - {k}: {p}")

    if manifest["status"] == "blocked":
        print(f"AVISO: Execução bloqueada. Motivo: {manifest['reason']}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
