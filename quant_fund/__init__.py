"""Núcleo quantitativo do fundo sistemático multi-sleeve."""

from .adapters import long_prices_to_wide, sec_facts_to_fundamentals
from .config import FundConfig, Sleeve1Config, Sleeve2Config
from .pipeline import PipelineResult, export_pipeline_result, run_pipeline
from .portfolio import build_fund_allocations, combine_security_weights
from .risk_overlay import (
    RiskOverlayConfig,
    build_risk_overlay,
    graded_allocations,
    hysteresis_state,
    insurance_ledger,
    rolling_zscore,
)
from .sleeve1 import Sleeve1Result, build_sleeve1
from .sleeve2 import Sleeve2Result, apply_hysteresis, build_sleeve2
from .sleeve3 import Sleeve3Result, build_sleeve3

__all__ = [
    "FundConfig",
    "PipelineResult",
    "RiskOverlayConfig",
    "Sleeve1Config",
    "Sleeve1Result",
    "Sleeve2Config",
    "Sleeve2Result",
    "Sleeve3Result",
    "apply_hysteresis",
    "build_fund_allocations",
    "build_risk_overlay",
    "build_sleeve1",
    "build_sleeve2",
    "build_sleeve3",
    "combine_security_weights",
    "export_pipeline_result",
    "graded_allocations",
    "hysteresis_state",
    "insurance_ledger",
    "long_prices_to_wide",
    "rolling_zscore",
    "run_pipeline",
    "sec_facts_to_fundamentals",
]
