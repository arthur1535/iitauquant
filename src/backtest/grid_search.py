"""Grid search local, paralelo, determinístico e retomável por Parquet."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from strategies.momentum_atr import MomentumATRConfig

from .engine import ExecutionConfig, run_backtest
from .statistics import deflated_sharpe_probability, expected_maximum_sharpe


@dataclass(frozen=True, slots=True)
class GridSearchConfig:
    momentum_windows: tuple[int, ...] = tuple(range(10, 65, 5))
    stop_multipliers: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 3.5)
    atr_windows: tuple[int, ...] = (14,)
    cost_per_side: float = 0.0015
    stop_slippage: float = 0.0
    annual_risk_free_rate: float = 0.0
    initial_capital: float = 1.0
    workers: int = field(default_factory=lambda: max(1, (os.cpu_count() or 2) - 1))
    batch_size: int = 100
    checkpoint_path: Path = Path("results/grid_search_checkpoint.parquet")

    def __post_init__(self) -> None:
        if not self.momentum_windows or not self.stop_multipliers or not self.atr_windows:
            raise ValueError("grades de momentum, stop e ATR não podem estar vazias")
        if self.workers < 1:
            raise ValueError("workers deve ser >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size deve ser >= 1")
        # Reutiliza as validações das configurações canônicas.
        ExecutionConfig(
            initial_capital=self.initial_capital,
            cost_per_side=self.cost_per_side,
            stop_slippage=self.stop_slippage,
            annual_risk_free_rate=self.annual_risk_free_rate,
        )
        for momentum, stop, atr in product(self.momentum_windows, self.stop_multipliers, self.atr_windows):
            MomentumATRConfig(momentum_window=momentum, atr_window=atr, stop_multiplier=stop)


@dataclass(frozen=True, slots=True)
class GridTask:
    ticker: str
    data_fingerprint: str
    momentum_window: int
    atr_window: int
    stop_multiplier: float
    cost_per_side: float
    stop_slippage: float
    annual_risk_free_rate: float
    initial_capital: float

    @property
    def task_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parquet_supported() -> bool:
    """Informa se existe um engine Parquet real no ambiente."""

    return importlib.util.find_spec("pyarrow") is not None or importlib.util.find_spec("fastparquet") is not None


def atomic_write_parquet(frame: pd.DataFrame, destination: str | Path) -> Path:
    """Grava no mesmo volume e troca o checkpoint somente após escrita completa."""

    if not parquet_supported():
        raise RuntimeError(
            "checkpoint Parquet requer 'pyarrow' ou 'fastparquet'; "
            "nenhum fallback com extensão enganosa é criado"
        )
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.parquet")
    try:
        frame.to_parquet(temporary, index=False)
        # No Windows, ``fsync`` requer descritor gravável; o Parquet já foi
        # fechado pelo pandas neste ponto.
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _read_checkpoint(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if not parquet_supported():
        raise RuntimeError("não é possível retomar Parquet sem pyarrow ou fastparquet")
    checkpoint = pd.read_parquet(path)
    if "task_id" not in checkpoint:
        raise ValueError(f"checkpoint inválido, sem task_id: {path}")
    if checkpoint["task_id"].duplicated().any():
        checkpoint = checkpoint.drop_duplicates("task_id", keep="last")
    return checkpoint


def _evaluate_worker(payload: tuple[GridTask, pd.DataFrame]) -> dict[str, Any]:
    task, data = payload
    strategy = MomentumATRConfig(
        momentum_window=task.momentum_window,
        atr_window=task.atr_window,
        stop_multiplier=task.stop_multiplier,
    )
    execution = ExecutionConfig(
        initial_capital=task.initial_capital,
        cost_per_side=task.cost_per_side,
        stop_slippage=task.stop_slippage,
        annual_risk_free_rate=task.annual_risk_free_rate,
    )
    result = run_backtest(data, strategy, execution)
    return {
        "task_id": task.task_id,
        "ticker": task.ticker,
        "data_fingerprint": task.data_fingerprint,
        "momentum_window": task.momentum_window,
        "atr_window": task.atr_window,
        "stop_multiplier": task.stop_multiplier,
        "cost_per_side": task.cost_per_side,
        "stop_slippage": task.stop_slippage,
        **result.metrics,
    }


def _data_fingerprint(data: pd.DataFrame) -> str:
    """Vincula a retomada ao conteúdo e ao índice exatos do dataset."""

    hashed = pd.util.hash_pandas_object(data, index=True).to_numpy(dtype="uint64", copy=False)
    return hashlib.sha256(hashed.tobytes()).hexdigest()


def _tasks_for(data_by_ticker: Mapping[str, pd.DataFrame], config: GridSearchConfig) -> list[GridTask]:
    fingerprints = {ticker: _data_fingerprint(data) for ticker, data in data_by_ticker.items()}
    tasks = [
        GridTask(
            ticker=ticker,
            data_fingerprint=fingerprints[ticker],
            momentum_window=momentum,
            atr_window=atr,
            stop_multiplier=stop,
            cost_per_side=config.cost_per_side,
            stop_slippage=config.stop_slippage,
            annual_risk_free_rate=config.annual_risk_free_rate,
            initial_capital=config.initial_capital,
        )
        for ticker in sorted(data_by_ticker)
        for momentum, stop, atr in product(
            sorted(set(config.momentum_windows)),
            sorted(set(config.stop_multipliers)),
            sorted(set(config.atr_windows)),
        )
    ]
    if not tasks:
        raise ValueError("data_by_ticker não pode estar vazio")
    return tasks


def _result_table(rows: Iterable[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.drop_duplicates("task_id", keep="last")
    frame["deflated_sharpe_ratio"] = float("nan")
    for _, positions in frame.groupby("ticker", sort=False).groups.items():
        group = frame.loc[positions]
        benchmark = expected_maximum_sharpe(
            float(group["sharpe_ratio"].std(ddof=1)),
            len(group),
        )
        frame.loc[positions, "deflated_sharpe_ratio"] = [
            deflated_sharpe_probability(
                float(row.sharpe_ratio),
                benchmark,
                n_observations=int(row.bars),
                skewness=float(row.return_skewness),
                kurtosis=float(row.return_kurtosis),
            )
            for row in group.itertuples()
        ]
    return frame.sort_values(
        ["sharpe_ratio", "total_return", "ticker", "momentum_window", "stop_multiplier", "atr_window"],
        ascending=[False, False, True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)


class GridSearchRunner:
    """Executa tarefas em processos e consolida checkpoints no processo pai."""

    def __init__(self, config: GridSearchConfig | None = None) -> None:
        self.config = config or GridSearchConfig()

    def run(self, data_by_ticker: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        if not parquet_supported():
            raise RuntimeError(
                "grid search retomável requer 'pyarrow' ou 'fastparquet' para o checkpoint Parquet"
            )
        tasks = _tasks_for(data_by_ticker, self.config)
        checkpoint_path = Path(self.config.checkpoint_path)
        existing = _read_checkpoint(checkpoint_path)
        wanted_ids = {task.task_id for task in tasks}
        if existing.empty:
            rows: list[dict[str, Any]] = []
            completed_ids: set[str] = set()
        else:
            existing = existing.loc[existing["task_id"].isin(wanted_ids)].copy()
            rows = existing.to_dict(orient="records")
            completed_ids = set(existing["task_id"].astype(str))

        pending = [task for task in tasks if task.task_id not in completed_ids]
        if not pending:
            return _result_table(rows)

        since_checkpoint = 0

        def accept(row: dict[str, Any]) -> None:
            nonlocal since_checkpoint
            rows.append(row)
            since_checkpoint += 1
            if since_checkpoint >= self.config.batch_size:
                atomic_write_parquet(_result_table(rows), checkpoint_path)
                since_checkpoint = 0

        try:
            if self.config.workers == 1 or len(pending) == 1:
                for task in pending:
                    accept(_evaluate_worker((task, data_by_ticker[task.ticker])))
            else:
                with ProcessPoolExecutor(max_workers=self.config.workers) as executor:
                    futures = {
                        executor.submit(_evaluate_worker, (task, data_by_ticker[task.ticker])): task
                        for task in pending
                    }
                    for future in as_completed(futures):
                        accept(future.result())
        except BaseException:
            if rows and since_checkpoint:
                atomic_write_parquet(_result_table(rows), checkpoint_path)
            raise

        result = _result_table(rows)
        atomic_write_parquet(result, checkpoint_path)
        return result
