"""Núcleo quantitativo do fundo sistemático multi-sleeve."""

from .adapters import long_prices_to_wide, sec_facts_to_fundamentals
from .config import FundConfig, Sleeve1Config, Sleeve2Config
from .pipeline import PipelineResult, export_pipeline_result, run_pipeline
from .portfolio import build_fund_allocations, combine_security_weights
from .sleeve1 import Sleeve1Result, build_sleeve1
from .sleeve2 import Sleeve2Result, apply_hysteresis, build_sleeve2
from .sleeve3 import Sleeve3Result, build_sleeve3

__all__ = [
    "FundConfig",
    "PipelineResult",
    "Sleeve1Config",
    "Sleeve1Result",
    "Sleeve2Config",
    "Sleeve2Result",
    "Sleeve3Result",
    "apply_hysteresis",
    "build_fund_allocations",
    "build_sleeve1",
    "build_sleeve2",
    "build_sleeve3",
    "combine_security_weights",
    "export_pipeline_result",
    "long_prices_to_wide",
    "run_pipeline",
    "sec_facts_to_fundamentals",
]
