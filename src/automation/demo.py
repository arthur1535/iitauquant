"""Explicit synthetic fixtures and an in-process signed webhook rehearsal."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.engine import ExecutionConfig, run_backtest
from strategies.momentum_atr import MomentumATRConfig

from .runner import atomic_json


def synthetic_history(bars: int = 420, seed: int = 42) -> pd.DataFrame:
    """Not market data. Oscillation and explicit gaps exercise both stop types."""
    rng = np.random.default_rng(seed)
    returns = 0.009 * np.sin(np.arange(bars) / 6) + rng.normal(0, 0.003, bars)
    close = 30 * np.exp(np.cumsum(returns))
    opening = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.001, bars))
    opening[150] *= 0.9
    frame = pd.DataFrame({
        "open": opening, "high": np.maximum(opening, close) * 1.005,
        "low": np.minimum(opening, close) * 0.995, "close": close,
        "volume": np.repeat(100000, bars),
    }, index=pd.bdate_range("2023-01-02", periods=bars, name="date"))
    return frame.round(5)


def create_demo_manifest(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    synthetic_history().to_parquet(output / "DEMO3.parquet")
    path = output / "universe.json"
    atomic_json(path, {
        "schema_version": 1, "as_of": "2024-08-09", "description": "SYNTHETIC FIXTURE ONLY",
        "data_policy": {"source": "synthetic_fixture", "adjustment": "none (synthetic)", "network_download": False},
        "universes": {"synthetic_only": ["DEMO3"]},
        "assets": {"DEMO3": {"local_file": "DEMO3.parquet", "status": "synthetic_fixture"}},
    })
    return path


def replay_paper_orders(frame: pd.DataFrame, output: Path) -> dict:
    """Replay historical fills inside TestClient with an isolated historical clock.

    This is not an exposed replay endpoint and does not alter live receiver time.
    The random secret exists only in this function, never on disk or in output.
    """
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from server.app import create_app
    from server.config import OmsSimulationConfig, RuntimeSettings

    strategy = MomentumATRConfig(momentum_window=10, atr_window=14, stop_multiplier=2)
    backtest = run_backtest(frame, strategy, ExecutionConfig(initial_capital=1000, liquidate_at_end=False))
    key = secrets.token_urlsafe(48)
    database = output / "paper_demo.sqlite3"
    if database.exists():
        raise FileExistsError("demo requires a new database; preserve prior evidence")
    oms = OmsSimulationConfig(
        mode="paper", database_path=database, allowed_symbols=frozenset({"DEMO3"}),
        max_quantity_per_order=10000, max_notional_brl_per_order=100000,
        replay_window_seconds=300, future_tolerance_seconds=30, max_body_bytes=65536,
        kill_switch=False, initial_cash_brl=1000,
        max_position_notional_brl=100000, max_gross_exposure_fraction=1,
    )
    now = [float(frame.index[0].tz_localize("UTC").timestamp())]
    app = create_app(RuntimeSettings(webhook_secret=SecretStr(key), oms=oms), clock=lambda: now[0])
    decisions = []
    reasons = {"momentum_cross": "MOMENTUM_ENTRY", "momentum_exit": "EXIT_MOMENTUM_LOSS",
               "gap_stop": "EXIT_STOP_TRIGGERED", "intraday_stop": "EXIT_STOP_TRIGGERED"}
    with TestClient(app) as client:
        for number, order in backtest.orders.iterrows():
            timestamp = pd.Timestamp(order["fill_time"]).tz_localize("UTC")
            now[0] = timestamp.timestamp()
            quantity = Decimal(str(order["quantity"])).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            price = Decimal(str(order["fill_price"])).quantize(Decimal("0.00000001"))
            payload = {
                "strategy": "MOMENTUM_ATR", "action": order["side"], "order_type": "MARKET",
                "ticker": "DEMO3", "close_price": str(price), "quantity": str(quantity),
                "timestamp": int(now[0] * 1000), "nonce": f"demo-nonce-{number:06d}",
                "idempotency_key": f"demo-event-{number:06d}", "reason": reasons[order["reason"]],
            }
            body = json.dumps(payload, separators=(",", ":")).encode()
            signature = "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
            headers = {"Content-Type": "application/json", "X-Webhook-Signature": signature}
            response = client.post("/webhook/tradingview", content=body, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"paper replay rejected event {number}: HTTP {response.status_code}")
            duplicate = client.post("/webhook/tradingview", content=body, headers=headers)
            if duplicate.status_code != 409:
                raise RuntimeError("replayed event was not rejected")
            decisions.append({"sequence": int(number), "side": order["side"], "accepted_http": 200, "duplicate_http": 409})
        invalid = client.post("/webhook/tradingview", content=b"{}", headers={"Content-Type": "application/json"})
        if invalid.status_code != 401:
            raise RuntimeError("unsigned request was not rejected")
        account_response = client.get("/paper/status", headers={"Authorization": "Bearer " + key})
        account_response.raise_for_status()
        account = account_response.json()
    reconciled_equity = Decimal(account["cash_brl"])
    for position in account["positions"].values():
        reconciled_equity += Decimal(position["quantity"]) * Decimal(str(frame["close"].iloc[-1]))
    difference = abs(float(reconciled_equity) - float(backtest.metrics["final_equity"]))
    if difference > 0.0001:
        raise RuntimeError("paper ledger does not reconcile with the backtest")
    backtest.orders.to_csv(output / "replayed_backtest_orders.csv", index=False)
    backtest.equity_curve.to_csv(output / "replayed_backtest_equity.csv")
    summary = {
        "source": "synthetic_fixture", "mode": "paper", "orders_accepted": len(decisions),
        "duplicates_rejected": len(decisions), "unsigned_http": invalid.status_code,
        "initial_cash_brl": 1000, "cost_per_side": 0.0015,
        "backtest_final_equity_brl": float(backtest.metrics["final_equity"]),
        "ledger_equity_at_final_candle_brl": str(reconciled_equity),
        "reconciliation_error_brl": difference,
        "account": account, "events": decisions,
        "clock": "isolated historical clock in TestClient; production clock unchanged",
        "broker_connected": False,
    }
    atomic_json(output / "paper_replay.json", summary)
    return summary


def run_demo(output_root: Path) -> dict:
    from .research import run_research

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
    output = output_root.resolve() / run_id
    output.mkdir(parents=True, exist_ok=False)
    manifest = create_demo_manifest(output / "fixture")
    research = run_research(manifest, output / "research", workers=1)
    replay = replay_paper_orders(synthetic_history(), output)
    result = {
        "status": research["status"], "mode": "paper", "source": "synthetic_fixture",
        "output_dir": str(output), "research": research, "replay": replay,
        "promotion_allowed": False, "additional_paid_services_used": False,
    }
    atomic_json(output / "demo.json", result)
    return result
