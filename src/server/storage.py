"""Immutable SQLite audit trail and paper-order repository."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import OmsSimulationConfig
from .models import TradingViewAlert
from .oms import evaluate_paper_order
from .paper_ledger import LedgerSnapshot, evaluate_portfolio, initialize_ledger, read_ledger


@dataclass(frozen=True, slots=True)
class StoreResult:
    duplicate: bool
    audit_event_id: int | None = None
    paper_order_id: int | None = None
    paper_fill_id: int | None = None
    accepted: bool = False
    http_status: int = 409
    detail: str = "duplicate or replayed webhook"
    notional_brl: Decimal = Decimal("0")
    fee_brl: Decimal = Decimal("0")
    cash_after_brl: Decimal | None = None


class AuditStore:
    """SQLite store whose business tables reject UPDATE and DELETE statements."""

    _IMMUTABLE_TABLES = ("webhook_receipts", "audit_events", "paper_orders", "paper_account", "paper_fills")

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            isolation_level=None,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self, initial_cash_brl: Decimal = Decimal("100000")) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(journal_mode).lower() != "wal":
                raise RuntimeError("SQLite WAL mode could not be enabled")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS webhook_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at_ms INTEGER NOT NULL,
                    event_timestamp_ms INTEGER NOT NULL,
                    nonce TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    CHECK(length(request_sha256) = 64)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at_ms INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    http_status INTEGER NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    idempotency_key TEXT,
                    nonce TEXT,
                    ticker TEXT,
                    action TEXT,
                    reason TEXT,
                    details_json TEXT NOT NULL,
                    CHECK(length(request_sha256) = 64)
                );

                CREATE TABLE IF NOT EXISTS paper_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id INTEGER NOT NULL UNIQUE,
                    audit_event_id INTEGER NOT NULL UNIQUE,
                    created_at_ms INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
                    order_type TEXT NOT NULL CHECK(order_type = 'MARKET'),
                    quantity TEXT NOT NULL,
                    reference_price TEXT NOT NULL,
                    notional_brl TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status = 'SIMULATED_ACCEPTED'),
                    execution_mode TEXT NOT NULL CHECK(execution_mode = 'paper'),
                    FOREIGN KEY(receipt_id) REFERENCES webhook_receipts(id),
                    FOREIGN KEY(audit_event_id) REFERENCES audit_events(id)
                );
                """
            )
            initialize_ledger(connection, initial_cash_brl)
            for table in self._IMMUTABLE_TABLES:
                connection.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_deny_update
                    BEFORE UPDATE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, '{table} is append-only');
                    END;
                    CREATE TRIGGER IF NOT EXISTS {table}_deny_delete
                    BEFORE DELETE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, '{table} is append-only');
                    END;
                    """
                )

    def ping(self) -> bool:
        try:
            with closing(self._connect()) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except sqlite3.Error:
            return False

    def paper_status(self) -> LedgerSnapshot:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                return read_ledger(connection)
            finally:
                connection.execute("ROLLBACK")

    @staticmethod
    def _details_json(details: dict[str, Any] | None) -> str:
        return json.dumps(details or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def append_audit_event(
        self,
        *,
        request_hash: str,
        outcome: str,
        http_status: int,
        event_type: str = "webhook",
        payload: TradingViewAlert | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """Append a metadata-only audit event; request bodies/signatures are not stored."""

        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_events (
                    received_at_ms, event_type, outcome, http_status, request_sha256,
                    idempotency_key, nonce, ticker, action, reason, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time() * 1_000),
                    event_type,
                    outcome,
                    http_status,
                    request_hash,
                    payload.idempotency_key if payload else None,
                    payload.nonce if payload else None,
                    payload.ticker if payload else None,
                    payload.action.value if payload else None,
                    payload.reason.value if payload else None,
                    self._details_json(details),
                ),
            )
            return int(cursor.lastrowid)

    def record_authenticated_decision(
        self,
        *,
        payload: TradingViewAlert,
        event_timestamp_ms: int,
        request_hash: str,
        config: OmsSimulationConfig,
    ) -> StoreResult:
        """Reserve keys, evaluate current risk, and append order/fill atomically.

        BEGIN IMMEDIATE serializes cash checks for simultaneous *different* orders
        as well as guaranteeing that retries cannot double-debit the paper account.
        Rejected authenticated requests also consume their replay keys.
        """

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now_ms = int(time.time() * 1_000)
            try:
                receipt_cursor = connection.execute(
                    """
                    INSERT INTO webhook_receipts (
                        received_at_ms, event_timestamp_ms, nonce, idempotency_key, request_sha256
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        now_ms,
                        event_timestamp_ms,
                        payload.nonce,
                        payload.idempotency_key,
                        request_hash,
                    ),
                )
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                duplicate_id = self.append_audit_event(
                    request_hash=request_hash,
                    outcome="duplicate_or_replay",
                    http_status=409,
                    payload=payload,
                    details={"detail": "nonce or idempotency key was already received"},
                )
                return StoreResult(duplicate=True, audit_event_id=duplicate_id)

            receipt_id = int(receipt_cursor.lastrowid)
            decision = evaluate_paper_order(payload, config)
            snapshot = read_ledger(connection)
            if decision.accepted:
                decision = evaluate_portfolio(payload, config, snapshot)
            notional = decision.notional
            fee = notional * config.cost_per_side if decision.accepted else Decimal("0")
            audit_cursor = connection.execute(
                """
                INSERT INTO audit_events (
                    received_at_ms, event_type, outcome, http_status, request_sha256,
                    idempotency_key, nonce, ticker, action, reason, details_json
                ) VALUES (?, 'webhook', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_ms,
                    decision.outcome,
                    decision.http_status,
                    request_hash,
                    payload.idempotency_key,
                    payload.nonce,
                    payload.ticker,
                    payload.action.value,
                    payload.reason.value,
                    self._details_json({"detail": decision.detail, "mode": "paper", "price_source": "ALERT_REFERENCE_SIMULATION", "fee_brl": str(fee)}),
                ),
            )
            audit_id = int(audit_cursor.lastrowid)
            paper_order_id: int | None = None
            paper_fill_id: int | None = None
            cash_after = snapshot.cash_brl
            if decision.accepted:
                order_cursor = connection.execute(
                    """
                    INSERT INTO paper_orders (
                        receipt_id, audit_event_id, created_at_ms, idempotency_key,
                        ticker, action, order_type, quantity, reference_price,
                        notional_brl, reason, status, execution_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SIMULATED_ACCEPTED', 'paper')
                    """,
                    (
                        receipt_id,
                        audit_id,
                        now_ms,
                        payload.idempotency_key,
                        payload.ticker,
                        payload.action.value,
                        payload.order_type,
                        str(payload.quantity),
                        str(payload.close_price),
                        str(notional),
                        payload.reason.value,
                    ),
                )
                paper_order_id = int(order_cursor.lastrowid)
                cash_delta = -(notional + fee) if payload.action.value == "BUY" else notional - fee
                fill_cursor = connection.execute(
                    """
                    INSERT INTO paper_fills (
                        paper_order_id, created_at_ms, ticker, action, quantity,
                        reference_price, notional_brl, fee_brl, cash_delta_brl,
                        cost_per_side, price_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ALERT_REFERENCE_SIMULATION')
                    """,
                    (paper_order_id, now_ms, payload.ticker, payload.action.value,
                     str(payload.quantity), str(payload.close_price), str(notional),
                     str(fee), str(cash_delta), str(config.cost_per_side)),
                )
                paper_fill_id = int(fill_cursor.lastrowid)
                cash_after += cash_delta
            connection.execute("COMMIT")
            return StoreResult(
                duplicate=False,
                audit_event_id=audit_id,
                paper_order_id=paper_order_id,
                paper_fill_id=paper_fill_id,
                accepted=decision.accepted,
                http_status=decision.http_status,
                detail=decision.detail,
                notional_brl=notional,
                fee_brl=fee,
                cash_after_brl=cash_after,
            )
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
