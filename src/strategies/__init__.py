"""Estratégias puras, sem integração com corretoras ou envio de ordens."""

from .momentum_atr import (
    MomentumATRConfig,
    average_true_range,
    build_momentum_atr_signals,
    true_range,
    validate_ohlc,
)

__all__ = [
    "MomentumATRConfig",
    "average_true_range",
    "build_momentum_atr_signals",
    "true_range",
    "validate_ohlc",
]
