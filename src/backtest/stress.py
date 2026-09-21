"""Matriz de estresse por universo, custos e slippage de stop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from strategies.momentum_atr import MomentumATRConfig

from .engine import ExecutionConfig, run_backtest


@dataclass(frozen=True, slots=True)
class StressScenario:
    name: str
    cost_per_side: float
    stop_slippage: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name não pode ser vazio")
        # Valida limites usando a fonte canônica.
        ExecutionConfig(cost_per_side=self.cost_per_side, stop_slippage=self.stop_slippage)


DEFAULT_STRESS_SCENARIOS = (
    StressScenario("base_15bps", cost_per_side=0.0015, stop_slippage=0.0),
    StressScenario("liquidez_reduzida", cost_per_side=0.0035, stop_slippage=0.0015),
    StressScenario("severo_50bps", cost_per_side=0.0050, stop_slippage=0.0030),
)


def run_stress_matrix(
    data_by_ticker: Mapping[str, pd.DataFrame],
    universes: Mapping[str, Iterable[str]],
    *,
    strategy_config: MomentumATRConfig | None = None,
    scenarios: Iterable[StressScenario] = DEFAULT_STRESS_SCENARIOS,
    annual_risk_free_rate: float = 0.0,
    strict: bool = True,
) -> pd.DataFrame:
    """Avalia combinações de universo/cenário sem baixar qualquer dado."""

    strategy = strategy_config or MomentumATRConfig()
    scenario_list = tuple(scenarios)
    if not scenario_list:
        raise ValueError("scenarios não pode estar vazio")
    rows: list[dict[str, float | int | str]] = []
    for universe_name, members in universes.items():
        for ticker in members:
            if ticker not in data_by_ticker:
                if strict:
                    raise KeyError(f"sem dados locais para {ticker} no universo {universe_name}")
                continue
            for scenario in scenario_list:
                execution = ExecutionConfig(
                    cost_per_side=scenario.cost_per_side,
                    stop_slippage=scenario.stop_slippage,
                    annual_risk_free_rate=annual_risk_free_rate,
                )
                result = run_backtest(data_by_ticker[ticker], strategy, execution)
                rows.append(
                    {
                        "universe": universe_name,
                        "scenario": scenario.name,
                        "ticker": ticker,
                        "cost_per_side": scenario.cost_per_side,
                        "stop_slippage": scenario.stop_slippage,
                        **result.metrics,
                    }
                )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["universe", "scenario", "ticker"], kind="mergesort").reset_index(drop=True)
