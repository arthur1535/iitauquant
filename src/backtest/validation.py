"""Partições temporais e validação walk-forward sem embaralhamento."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable

import numpy as np
import pandas as pd

from strategies.momentum_atr import MomentumATRConfig, validate_ohlc

from .engine import BacktestResult, ExecutionConfig, run_backtest


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train: pd.DataFrame
    test: pd.DataFrame
    split_position: int
    split_timestamp: pd.Timestamp


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold: int
    train_indices: np.ndarray
    purge_indices: np.ndarray
    test_indices: np.ndarray
    embargo_indices: np.ndarray


@dataclass(slots=True)
class HoldoutValidation:
    ranking_in_sample: pd.DataFrame
    best_strategy: MomentumATRConfig
    in_sample: BacktestResult
    out_of_sample: BacktestResult


def chronological_split(data: pd.DataFrame, train_fraction: float = 0.70) -> TemporalSplit:
    """Divide por posição, preservando 70% IS e 30% OOS por padrão."""

    frame = validate_ohlc(data)
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction deve estar estritamente entre 0 e 1")
    split_position = int(np.floor(len(frame) * train_fraction))
    if split_position < 1 or split_position >= len(frame):
        raise ValueError("a amostra precisa conter ao menos uma barra em cada partição")
    return TemporalSplit(
        train=frame.iloc[:split_position].copy(),
        test=frame.iloc[split_position:].copy(),
        split_position=split_position,
        split_timestamp=frame.index[split_position],
    )


def purged_walk_forward_splits(
    n_samples: int,
    *,
    train_size: int,
    test_size: int,
    purge: int = 1,
    embargo: int = 5,
    expanding: bool = True,
) -> list[WalkForwardFold]:
    """Gera folds estritamente ordenados com purge antes e embargo após o teste.

    O embargo desloca o início do próximo teste. Em modo expansivo, observações
    de testes anteriores podem integrar treinos futuros, o que é causal porque já
    eram conhecidas naquele ponto do tempo.
    """

    for name, value in {
        "n_samples": n_samples,
        "train_size": train_size,
        "test_size": test_size,
    }.items():
        if value < 1:
            raise ValueError(f"{name} deve ser >= 1")
    if purge < 0 or embargo < 0:
        raise ValueError("purge e embargo devem ser >= 0")
    if train_size + purge >= n_samples:
        return []

    folds: list[WalkForwardFold] = []
    test_start = train_size + purge
    fold_number = 0
    while test_start < n_samples:
        train_end = test_start - purge
        train_start = 0 if expanding else max(0, train_end - train_size)
        test_end = min(test_start + test_size, n_samples)
        embargo_end = min(test_end + embargo, n_samples)
        folds.append(
            WalkForwardFold(
                fold=fold_number,
                train_indices=np.arange(train_start, train_end, dtype=int),
                purge_indices=np.arange(train_end, test_start, dtype=int),
                test_indices=np.arange(test_start, test_end, dtype=int),
                embargo_indices=np.arange(test_end, embargo_end, dtype=int),
            )
        )
        fold_number += 1
        test_start = test_end + embargo
    return folds


def _parameter_candidates(
    momentum_windows: Iterable[int],
    stop_multipliers: Iterable[float],
    atr_windows: Iterable[int],
) -> list[MomentumATRConfig]:
    candidates = [
        MomentumATRConfig(momentum_window=mom, atr_window=atr, stop_multiplier=stop)
        for mom, stop, atr in product(
            sorted(set(momentum_windows)),
            sorted(set(stop_multipliers)),
            sorted(set(atr_windows)),
        )
    ]
    if not candidates:
        raise ValueError("a grade de parâmetros não pode estar vazia")
    return candidates


def _rank_interval(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    candidates: Iterable[MomentumATRConfig],
    execution: ExecutionConfig,
) -> tuple[pd.DataFrame, MomentumATRConfig, BacktestResult]:
    rows: list[dict[str, float | int]] = []
    results: list[tuple[MomentumATRConfig, BacktestResult]] = []
    for candidate in candidates:
        result = run_backtest(data, candidate, execution, trade_start=start, trade_end=end)
        results.append((candidate, result))
        rows.append(
            {
                "momentum_window": candidate.momentum_window,
                "atr_window": candidate.atr_window,
                "stop_multiplier": candidate.stop_multiplier,
                **result.metrics,
            }
        )
    ranking = pd.DataFrame(rows).sort_values(
        ["sharpe_ratio", "total_return", "momentum_window", "stop_multiplier", "atr_window"],
        ascending=[False, False, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    best_row = ranking.iloc[0]
    best = MomentumATRConfig(
        momentum_window=int(best_row["momentum_window"]),
        atr_window=int(best_row["atr_window"]),
        stop_multiplier=float(best_row["stop_multiplier"]),
    )
    best_result = next(result for candidate, result in results if candidate == best)
    return ranking, best, best_result


def validate_70_30(
    data: pd.DataFrame,
    *,
    momentum_windows: Iterable[int],
    stop_multipliers: Iterable[float],
    atr_windows: Iterable[int] = (14,),
    execution_config: ExecutionConfig | None = None,
) -> HoldoutValidation:
    """Seleciona parâmetros somente nos 70% IS e avalia uma vez nos 30% OOS."""

    frame = validate_ohlc(data)
    split = chronological_split(frame, 0.70)
    execution = execution_config or ExecutionConfig()
    candidates = _parameter_candidates(momentum_windows, stop_multipliers, atr_windows)
    ranking, best, in_sample = _rank_interval(
        frame,
        frame.index[0],
        split.train.index[-1],
        candidates,
        execution,
    )
    out_of_sample = run_backtest(
        frame,
        best,
        execution,
        trade_start=split.test.index[0],
        trade_end=split.test.index[-1],
    )
    return HoldoutValidation(ranking, best, in_sample, out_of_sample)


def walk_forward_validate(
    data: pd.DataFrame,
    *,
    momentum_windows: Iterable[int],
    stop_multipliers: Iterable[float],
    atr_windows: Iterable[int] = (14,),
    train_size: int,
    test_size: int,
    purge: int = 1,
    embargo: int = 5,
    expanding: bool = True,
    execution_config: ExecutionConfig | None = None,
) -> pd.DataFrame:
    """Recalibra em cada janela IS e reporta apenas desempenho OOS cego."""

    frame = validate_ohlc(data)
    folds = purged_walk_forward_splits(
        len(frame),
        train_size=train_size,
        test_size=test_size,
        purge=purge,
        embargo=embargo,
        expanding=expanding,
    )
    if not folds:
        raise ValueError("dados insuficientes para formar um fold walk-forward")
    candidates = _parameter_candidates(momentum_windows, stop_multipliers, atr_windows)
    execution = execution_config or ExecutionConfig()
    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for fold in folds:
        train_start = frame.index[fold.train_indices[0]]
        train_end = frame.index[fold.train_indices[-1]]
        test_start = frame.index[fold.test_indices[0]]
        test_end = frame.index[fold.test_indices[-1]]
        _, best, in_sample = _rank_interval(frame, train_start, train_end, candidates, execution)
        out_of_sample = run_backtest(
            frame,
            best,
            execution,
            trade_start=test_start,
            trade_end=test_end,
        )
        is_sharpe = float(in_sample.metrics["sharpe_ratio"])
        oos_sharpe = float(out_of_sample.metrics["sharpe_ratio"])
        efficiency = oos_sharpe / is_sharpe if abs(is_sharpe) > 1e-15 else np.nan
        rows.append(
            {
                "fold": fold.fold,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "momentum_window": best.momentum_window,
                "atr_window": best.atr_window,
                "stop_multiplier": best.stop_multiplier,
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "walk_forward_efficiency": efficiency,
                "oos_total_return": out_of_sample.metrics["total_return"],
                "oos_max_drawdown": out_of_sample.metrics["max_drawdown"],
                "oos_total_trades": out_of_sample.metrics["total_trades"],
            }
        )
    return pd.DataFrame(rows)
