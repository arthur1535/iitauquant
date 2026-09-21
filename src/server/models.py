"""Pydantic v2 contracts for TradingView webhook events."""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .config import normalize_symbol


OpaqueKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:@+-]+$",
    ),
]


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Reason(str, Enum):
    MOMENTUM_ENTRY = "MOMENTUM_ENTRY"
    EXIT_STOP_TRIGGERED = "EXIT_STOP_TRIGGERED"
    EXIT_MOMENTUM_LOSS = "EXIT_MOMENTUM_LOSS"


class WebhookMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    exchange: str | None = Field(default=None, max_length=32)
    interval: str | None = Field(default=None, max_length=32)
    bar_time: str | int | None = None


class TradingViewAlert(BaseModel):
    """Authenticated command accepted by the paper OMS.

    ``timestamp`` supports TradingView's ISO-8601 ``{{timenow}}`` output as well as
    epoch seconds/milliseconds.  It is normalized only for replay validation, so the
    signed raw request body is never rewritten before HMAC verification.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    strategy: Literal["MOMENTUM_ATR"]
    action: Action
    order_type: Literal["MARKET"] = "MARKET"
    ticker: str = Field(min_length=1, max_length=32)
    close_price: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    stop_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    timestamp: int | str
    nonce: OpaqueKey
    idempotency_key: OpaqueKey
    reason: Reason
    metadata: WebhookMetadata | None = None

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("order_type", mode="before")
    @classmethod
    def normalize_order_type(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        symbol = normalize_symbol(value)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,15}", symbol):
            raise ValueError("ticker has an invalid format")
        return symbol

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_shape(cls, value: int | str) -> int | str:
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("timestamp must be positive")
            return value
        if not value.strip() or len(value) > 64:
            raise ValueError("timestamp must be a non-empty epoch or ISO-8601 value")
        return value.strip()

    @model_validator(mode="after")
    def validate_action_reason(self) -> "TradingViewAlert":
        if self.reason is Reason.MOMENTUM_ENTRY and self.action is not Action.BUY:
            raise ValueError("MOMENTUM_ENTRY requires action BUY")
        if self.reason is not Reason.MOMENTUM_ENTRY and self.action is not Action.SELL:
            raise ValueError("exit reasons require action SELL")
        return self


class PaperOrderResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    mode: Literal["paper"] = "paper"
    execution: Literal["SIMULATED_ONLY"] = "SIMULATED_ONLY"
    paper_order_id: int
    idempotency_key: str
    ticker: str
    action: Action
    notional_brl: str
    paper_fill_id: int
    fee_brl: str
    cash_after_brl: str
    price_source: Literal["ALERT_REFERENCE_SIMULATION"] = "ALERT_REFERENCE_SIMULATION"
