"""Local paper accounting derived from immutable reference-price fills.

Prices are received in authenticated alerts. They are neither live broker quotes
nor a claim that an order would fill at that price. Monetary arithmetic is Decimal;
fees retain full precision because no real brokerage currency rounding is modeled.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from decimal import Decimal

from .config import OmsSimulationConfig
from .models import Action, TradingViewAlert
from .oms import RiskDecision


ZERO = Decimal("0")
PRICE_SOURCE = "ALERT_REFERENCE_SIMULATION"


@dataclass(slots=True)
class PaperPosition:
    quantity: Decimal = ZERO
    cost_basis_brl: Decimal = ZERO
    reference_price_brl: Decimal = ZERO

    @property
    def market_value_brl(self) -> Decimal:
        return self.quantity * self.reference_price_brl


@dataclass(slots=True)
class LedgerSnapshot:
    initial_cash_brl: Decimal
    cash_brl: Decimal
    fees_paid_brl: Decimal = ZERO
    realized_pnl_brl: Decimal = ZERO
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    fill_count: int = 0
    legacy_unfilled_order_count: int = 0

    @property
    def gross_exposure_brl(self) -> Decimal:
        return sum((p.market_value_brl for p in self.positions.values()), ZERO)

    @property
    def equity_reference_brl(self) -> Decimal:
        return self.cash_brl + self.gross_exposure_brl

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": "paper",
            "execution": "SIMULATED_ONLY",
            "ledger_status": "legacy_orders_require_review" if self.legacy_unfilled_order_count else "ready",
            "price_source": PRICE_SOURCE,
            "valuation_note": "Last alert fill prices, potentially stale; not live market quotes or executable broker prices.",
            "initial_cash_brl": str(self.initial_cash_brl),
            "cash_brl": str(self.cash_brl),
            "gross_exposure_brl": str(self.gross_exposure_brl),
            "equity_reference_brl": str(self.equity_reference_brl),
            "fees_paid_brl": str(self.fees_paid_brl),
            "realized_pnl_brl": str(self.realized_pnl_brl),
            "unrealized_reference_pnl_brl": str(sum((p.market_value_brl - p.cost_basis_brl for p in self.positions.values()), ZERO)),
            "fill_count": self.fill_count,
            "legacy_unfilled_order_count": self.legacy_unfilled_order_count,
            "positions": {
                ticker: {
                    "quantity": str(position.quantity),
                    "cost_basis_brl": str(position.cost_basis_brl),
                    "average_cost_brl": str(position.cost_basis_brl / position.quantity),
                    "reference_price_brl": str(position.reference_price_brl),
                    "reference_value_brl": str(position.market_value_brl),
                    "unrealized_reference_pnl_brl": str(position.market_value_brl - position.cost_basis_brl),
                }
                for ticker, position in sorted(self.positions.items())
                if position.quantity > ZERO
            },
        }


def initialize_ledger(connection: sqlite3.Connection, initial_cash_brl: Decimal) -> None:
    """Create an immutable account seed, without replaying any legacy paper orders."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS paper_account (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            created_at_ms INTEGER NOT NULL,
            initial_cash_brl TEXT NOT NULL,
            currency TEXT NOT NULL CHECK(currency = 'BRL'),
            execution_mode TEXT NOT NULL CHECK(execution_mode = 'paper'),
            ledger_version INTEGER NOT NULL CHECK(ledger_version = 1)
        );
        CREATE TABLE IF NOT EXISTS paper_fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_order_id INTEGER NOT NULL UNIQUE REFERENCES paper_orders(id),
            created_at_ms INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
            quantity TEXT NOT NULL,
            reference_price TEXT NOT NULL,
            notional_brl TEXT NOT NULL,
            fee_brl TEXT NOT NULL,
            cash_delta_brl TEXT NOT NULL,
            cost_per_side TEXT NOT NULL,
            price_source TEXT NOT NULL CHECK(price_source = 'ALERT_REFERENCE_SIMULATION')
        );
        """
    )
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT OR IGNORE INTO paper_account VALUES (1, ?, ?, 'BRL', 'paper', 1)",
            (int(time.time() * 1000), str(initial_cash_brl)),
        )
        seed = connection.execute("SELECT initial_cash_brl FROM paper_account WHERE id = 1").fetchone()
        if Decimal(seed[0]) != initial_cash_brl:
            raise RuntimeError("initial_cash_brl differs from the immutable paper account; use its original setting or a new database")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def read_ledger(connection: sqlite3.Connection) -> LedgerSnapshot:
    """Read one database snapshot; callers hold a read or immediate transaction."""
    initial = Decimal(connection.execute("SELECT initial_cash_brl FROM paper_account WHERE id = 1").fetchone()[0])
    snapshot = LedgerSnapshot(initial_cash_brl=initial, cash_brl=initial)
    snapshot.legacy_unfilled_order_count = connection.execute(
        "SELECT count(*) FROM paper_orders o LEFT JOIN paper_fills f ON f.paper_order_id = o.id WHERE f.id IS NULL"
    ).fetchone()[0]
    for row in connection.execute(
        "SELECT ticker, action, quantity, reference_price, notional_brl, fee_brl, cash_delta_brl FROM paper_fills ORDER BY id"
    ):
        ticker, action = row[:2]
        quantity, price, notional, fee, cash_delta = (Decimal(value) for value in row[2:])
        position = snapshot.positions.setdefault(ticker, PaperPosition())
        position.reference_price_brl = price
        if action == "BUY":
            position.quantity += quantity
            position.cost_basis_brl += notional + fee
        else:
            if quantity > position.quantity or position.quantity <= ZERO:
                raise RuntimeError("paper ledger contains a short sale; manual integrity review required")
            removed_basis = position.cost_basis_brl if quantity == position.quantity else position.cost_basis_brl * quantity / position.quantity
            position.quantity -= quantity
            position.cost_basis_brl -= removed_basis
            snapshot.realized_pnl_brl += cash_delta - removed_basis
        snapshot.cash_brl += cash_delta
        snapshot.fees_paid_brl += fee
        snapshot.fill_count += 1
    if snapshot.cash_brl < ZERO:
        raise RuntimeError("paper ledger has negative cash; manual integrity review required")
    return snapshot


def evaluate_portfolio(
    payload: TradingViewAlert, config: OmsSimulationConfig, snapshot: LedgerSnapshot
) -> RiskDecision:
    """Evaluate cash/holdings inside the same write transaction as the resulting fill."""
    notional = payload.quantity * payload.close_price

    def reject(outcome: str, detail: str, status: int = 422) -> RiskDecision:
        return RiskDecision(False, status, outcome, detail, notional)

    if snapshot.legacy_unfilled_order_count:
        return reject("legacy_ledger_review_required", "legacy paper orders have no ledger fills; reconcile explicitly or use a new database", 503)
    held = snapshot.positions.get(payload.ticker, PaperPosition())
    if payload.action is Action.SELL:
        if payload.quantity > held.quantity:
            return reject("insufficient_position", "sell quantity exceeds the held paper position; short sales are disabled")
    else:
        fee = notional * config.cost_per_side
        if notional + fee > snapshot.cash_brl:
            return reject("insufficient_cash", "insufficient paper cash including transaction costs")
        open_positions = sum(p.quantity > ZERO for p in snapshot.positions.values())
        if held.quantity == ZERO and open_positions >= config.max_positions:
            return reject("position_count_limit", "maximum number of open paper positions reached")
        position_value = (held.quantity + payload.quantity) * payload.close_price
        if position_value > config.max_position_notional_brl:
            return reject("position_notional_limit", "position would exceed the configured reference notional limit")
        # Refresh only the submitted symbol; other marks remain explicitly stale.
        prior_gross = snapshot.gross_exposure_brl - held.market_value_brl + held.quantity * payload.close_price
        gross_after = prior_gross + notional
        equity_after = snapshot.cash_brl + prior_gross - fee
        if gross_after > equity_after * config.max_gross_exposure_fraction:
            return reject("gross_exposure_limit", "portfolio would exceed the configured reference gross exposure fraction")
    return RiskDecision(True, 200, "paper_order_accepted", "filled locally at the alert reference price; no live broker execution", notional)
