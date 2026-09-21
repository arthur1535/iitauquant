"""Infraestrutura de simulação quantitativa local e auditável."""

from .engine import BacktestResult, ExecutionConfig, calculate_performance_metrics, run_backtest
from .grid_search import GridSearchConfig, GridSearchRunner, atomic_write_parquet, parquet_supported
from .statistics import deflated_sharpe_probability, expected_maximum_sharpe
from .stress import DEFAULT_STRESS_SCENARIOS, StressScenario, run_stress_matrix
from .universe import (
    AssetRecord,
    UniverseManifest,
    load_local_history,
    load_local_universe,
    load_universe_manifest,
)
from .validation import (
    HoldoutValidation,
    TemporalSplit,
    WalkForwardFold,
    chronological_split,
    purged_walk_forward_splits,
    validate_70_30,
    walk_forward_validate,
)

__all__ = [
    "AssetRecord",
    "BacktestResult",
    "DEFAULT_STRESS_SCENARIOS",
    "ExecutionConfig",
    "GridSearchConfig",
    "GridSearchRunner",
    "HoldoutValidation",
    "StressScenario",
    "TemporalSplit",
    "UniverseManifest",
    "WalkForwardFold",
    "atomic_write_parquet",
    "calculate_performance_metrics",
    "chronological_split",
    "deflated_sharpe_probability",
    "expected_maximum_sharpe",
    "load_local_history",
    "load_local_universe",
    "load_universe_manifest",
    "parquet_supported",
    "purged_walk_forward_splits",
    "run_backtest",
    "run_stress_matrix",
    "validate_70_30",
    "walk_forward_validate",
]
