"""Otimização Bayesiana opcional e reproduzível via Optuna."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from strategies.momentum_atr import MomentumATRConfig

from .engine import ExecutionConfig, run_backtest


@dataclass(frozen=True, slots=True)
class OptunaConfig:
    n_trials: int = 100
    seed: int = 42
    momentum_min: int = 10
    momentum_max: int = 60
    momentum_step: int = 5
    stop_min: float = 1.5
    stop_max: float = 3.5
    stop_step: float = 0.5
    atr_window: int = 14

    def __post_init__(self) -> None:
        if self.n_trials < 1:
            raise ValueError("n_trials deve ser >= 1")
        if self.momentum_min < 1 or self.momentum_max < self.momentum_min or self.momentum_step < 1:
            raise ValueError("intervalo de momentum inválido")
        if self.stop_min <= 0 or self.stop_max < self.stop_min or self.stop_step <= 0:
            raise ValueError("intervalo de stop inválido")


def optimize_with_optuna(
    data: pd.DataFrame,
    *,
    config: OptunaConfig | None = None,
    execution_config: ExecutionConfig | None = None,
    trade_start: Any = None,
    trade_end: Any = None,
) -> tuple[Any, pd.DataFrame]:
    """Maximiza Sharpe; importa Optuna apenas quando a função é usada."""

    try:
        import optuna
    except ImportError as error:
        raise RuntimeError("otimização opcional requer o pacote 'optuna'") from error

    search = config or OptunaConfig()
    execution = execution_config or ExecutionConfig()

    def objective(trial: Any) -> float:
        strategy = MomentumATRConfig(
            momentum_window=trial.suggest_int(
                "momentum_window",
                search.momentum_min,
                search.momentum_max,
                step=search.momentum_step,
            ),
            atr_window=search.atr_window,
            stop_multiplier=trial.suggest_float(
                "stop_multiplier",
                search.stop_min,
                search.stop_max,
                step=search.stop_step,
            ),
        )
        result = run_backtest(
            data,
            strategy,
            execution,
            trade_start=trade_start,
            trade_end=trade_end,
        )
        for key, value in result.metrics.items():
            if isinstance(value, (int, float)):
                trial.set_user_attr(key, value)
        return float(result.metrics["sharpe_ratio"])

    sampler = optuna.samplers.TPESampler(seed=search.seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=search.n_trials)
    rows = [
        {
            "trial": trial.number,
            "state": trial.state.name,
            "value": trial.value,
            **trial.params,
            **trial.user_attrs,
        }
        for trial in study.trials
    ]
    return study, pd.DataFrame(rows).sort_values("trial").reset_index(drop=True)
