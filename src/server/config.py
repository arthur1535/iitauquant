"""Configuration for the simulation-only OMS.

The webhook secret is deliberately absent from the JSON configuration.  It must be
provided through ``TRADINGVIEW_WEBHOOK_SECRET`` at process start.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "oms_simulation.json"
_REJECTED_SECRETS = {
    "changeme",
    "change-me",
    "secret",
    "your_secure_webhook_passphrase_here",
}
_REJECTED_SECRET_PREFIXES = ("replace-with-", "replace_with_", "your-secret-", "your_secure_")


def normalize_symbol(value: str) -> str:
    """Normalize a TradingView/B3 symbol for allowlist comparisons."""

    symbol = value.strip().upper()
    if ":" in symbol:
        _, symbol = symbol.rsplit(":", 1)
    return symbol


class OmsSimulationConfig(BaseModel):
    """Non-secret operational limits for the paper OMS."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    mode: Literal["paper"]
    database_path: Path
    allowed_symbols: frozenset[str] = Field(min_length=1)
    max_quantity_per_order: float = Field(gt=0, allow_inf_nan=False)
    max_notional_brl_per_order: float = Field(gt=0, allow_inf_nan=False)
    replay_window_seconds: int = Field(ge=30, le=3_600)
    future_tolerance_seconds: int = Field(ge=0, le=300)
    max_body_bytes: int = Field(ge=1_024, le=1_048_576)
    kill_switch: bool
    kill_switch_path: Path | None = None
    initial_cash_brl: Decimal = Field(default=Decimal("100000"), gt=0, max_digits=18, decimal_places=2)
    cost_per_side: Decimal = Field(default=Decimal("0.0015"), ge=Decimal("0.0015"), lt=1)
    max_position_notional_brl: Decimal = Field(default=Decimal("30000"), gt=0)
    max_gross_exposure_fraction: Decimal = Field(default=Decimal("0.95"), gt=0, le=1)
    max_positions: int = Field(default=10, ge=1, le=1000)

    @field_validator("allowed_symbols", mode="before")
    @classmethod
    def validate_allowed_symbols(cls, value: object) -> frozenset[str]:
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError("allowed_symbols must be a non-empty JSON array")
        normalized = frozenset(
            normalize_symbol(item) for item in value if isinstance(item, str) and item.strip()
        )
        if not normalized:
            raise ValueError("allowed_symbols must contain at least one symbol")
        return normalized


class RuntimeSettings(BaseModel):
    """Validated runtime settings with a redacted secret representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    webhook_secret: SecretStr
    oms: OmsSimulationConfig

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw.encode("utf-8")) < 32:
            raise ValueError("TRADINGVIEW_WEBHOOK_SECRET must be at least 32 bytes")
        normalized = raw.strip().lower()
        if normalized in _REJECTED_SECRETS or normalized.startswith(_REJECTED_SECRET_PREFIXES):
            raise ValueError("TRADINGVIEW_WEBHOOK_SECRET is an unsafe placeholder")
        return value


def _parse_bool_env(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def load_runtime_settings(config_path: Path | str | None = None) -> RuntimeSettings:
    """Load settings, failing closed when the required secret is absent."""

    secret = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("TRADINGVIEW_WEBHOOK_SECRET is required")

    selected_path = Path(
        config_path or os.environ.get("OMS_SIMULATION_CONFIG", DEFAULT_CONFIG_PATH)
    ).expanduser()
    try:
        raw_config = json.loads(selected_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"OMS simulation config not found: {selected_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OMS simulation config is invalid JSON: {selected_path}") from exc

    oms = OmsSimulationConfig.model_validate(raw_config)
    database_path = oms.database_path
    if not database_path.is_absolute():
        database_path = (PROJECT_ROOT / database_path).resolve()

    kill_switch_override = os.environ.get("OMS_KILL_SWITCH")
    updates: dict[str, object] = {"database_path": database_path}
    if oms.kill_switch_path is not None:
        marker = oms.kill_switch_path
        updates["kill_switch_path"] = marker if marker.is_absolute() else (PROJECT_ROOT / marker).resolve()
    if kill_switch_override is not None:
        updates["kill_switch"] = _parse_bool_env("OMS_KILL_SWITCH", kill_switch_override)
    oms = oms.model_copy(update=updates)
    return RuntimeSettings(webhook_secret=SecretStr(secret), oms=oms)
