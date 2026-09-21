"""Fail-closed risk gate for the simulation-only OMS."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .config import OmsSimulationConfig
from .models import TradingViewAlert


@dataclass(frozen=True, slots=True)
class RiskDecision:
    accepted: bool
    http_status: int
    outcome: str
    detail: str
    notional: Decimal


def kill_switch_active(config: OmsSimulationConfig) -> bool:
    """A local marker file pauses all orders immediately; filesystem errors fail closed.

    Creating ``kill_switch_path`` activates it and removing that file deactivates it.
    A statically configured kill switch always takes precedence.
    """
    if config.kill_switch:
        return True
    if config.kill_switch_path is None:
        return False
    try:
        config.kill_switch_path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def evaluate_paper_order(
    payload: TradingViewAlert, config: OmsSimulationConfig
) -> RiskDecision:
    """Evaluate configured limits without any live broker side effect."""

    notional = payload.close_price * payload.quantity
    if kill_switch_active(config):
        return RiskDecision(
            False,
            503,
            "kill_switch",
            "paper OMS kill switch is active",
            notional,
        )
    if payload.ticker not in config.allowed_symbols:
        return RiskDecision(False, 403, "symbol_blocked", "ticker is not in the allowlist", notional)
    if payload.quantity > Decimal(str(config.max_quantity_per_order)):
        return RiskDecision(
            False,
            422,
            "quantity_limit",
            "quantity exceeds the configured paper-order limit",
            notional,
        )
    if notional > Decimal(str(config.max_notional_brl_per_order)):
        return RiskDecision(
            False,
            422,
            "notional_limit",
            "notional exceeds the configured paper-order limit",
            notional,
        )
    return RiskDecision(True, 200, "paper_order_accepted", "simulation only", notional)
