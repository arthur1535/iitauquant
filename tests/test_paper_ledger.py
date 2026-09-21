from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from src.server.app import create_app
from src.server.config import OmsSimulationConfig, RuntimeSettings, load_runtime_settings
from src.server.oms import kill_switch_active


NOW = 1_800_000_000.0
SECRET = "local-ledger-test-secret-with-at-least-32-bytes"
AUTH = {"Authorization": f"Bearer {SECRET}"}


def settings(path: Path, **overrides: object) -> RuntimeSettings:
    values = {
        "mode": "paper", "database_path": path,
        "allowed_symbols": ["PETR4", "VALE3"],
        "max_quantity_per_order": 10_000,
        "max_notional_brl_per_order": 1_000_000,
        "max_position_notional_brl": "1000000",
        "max_gross_exposure_fraction": "1",
        "replay_window_seconds": 300, "future_tolerance_seconds": 30,
        "max_body_bytes": 65_536, "kill_switch": False,
    }
    values.update(overrides)
    return RuntimeSettings(webhook_secret=SecretStr(SECRET), oms=OmsSimulationConfig(**values))


def order(client: TestClient, key: int, *, side: str = "BUY", quantity: object = 100, price: object = 10, ticker: str = "PETR4"):
    body = json.dumps({
        "strategy": "MOMENTUM_ATR", "action": side, "order_type": "MARKET",
        "ticker": ticker, "close_price": price, "quantity": quantity,
        "timestamp": int(NOW * 1000), "nonce": f"paper-nonce-{key:08d}",
        "idempotency_key": f"paper-order-{key:08d}",
        "reason": "MOMENTUM_ENTRY" if side == "BUY" else "EXIT_MOMENTUM_LOSS",
    }, separators=(",", ":")).encode()
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook/tradingview", content=body, headers={
        "Content-Type": "application/json", "X-Webhook-Signature": f"sha256={signature}",
    })


def report(client: TestClient) -> dict[str, object]:
    response = client.get("/paper/status", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def count(path: Path, table: str) -> int:
    assert table in {"paper_fills", "paper_orders", "webhook_receipts", "audit_events"}
    with sqlite3.connect(path) as connection:
        return connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_buy_partial_sell_and_close_reconcile_fees_basis_and_pnl(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3"), clock=lambda: NOW)) as client:
        buy = order(client, 1)
        assert buy.status_code == 200
        assert Decimal(buy.json()["fee_brl"]) == Decimal("1.5")
        assert Decimal(report(client)["cash_brl"]) == Decimal("98998.5")
        assert order(client, 2, side="SELL", quantity=40, price=12).status_code == 200
        partial = report(client)
        assert Decimal(partial["cash_brl"]) == Decimal("99477.78")
        assert Decimal(partial["realized_pnl_brl"]) == Decimal("78.68")
        assert Decimal(partial["positions"]["PETR4"]["cost_basis_brl"]) == Decimal("600.9")
        assert Decimal(partial["equity_reference_brl"]) == Decimal("100197.78")
        assert order(client, 3, side="SELL", quantity=60, price=9).status_code == 200
        closed = report(client)
    assert closed["positions"] == {}
    assert Decimal(closed["cash_brl"]) == Decimal("100016.97")
    assert Decimal(closed["realized_pnl_brl"]) == Decimal("16.97")
    assert Decimal(closed["fees_paid_brl"]) == Decimal("3.03")
    assert closed["fill_count"] == 3
    assert closed["price_source"] == "ALERT_REFERENCE_SIMULATION"
    assert "stale" in closed["valuation_note"]


def test_cash_check_includes_fees_and_rejected_keys_are_consumed(tmp_path: Path) -> None:
    path = tmp_path / "oms.sqlite3"
    with TestClient(create_app(settings(path, initial_cash_brl="1000"), clock=lambda: NOW)) as client:
        response = order(client, 1, quantity=100, price=10)
        assert response.status_code == 422
        assert "including transaction costs" in response.json()["detail"]
        assert order(client, 1, quantity=10).status_code == 409
        state = report(client)
    assert Decimal(state["cash_brl"]) == 1000
    assert state["fill_count"] == 0
    assert count(path, "paper_orders") == 0
    assert count(path, "webhook_receipts") == 1


def test_no_short_sales_or_overselling_and_valid_exit_still_works(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3"), clock=lambda: NOW)) as client:
        assert order(client, 1, side="SELL").status_code == 422
        assert order(client, 2, quantity=10).status_code == 200
        assert order(client, 3, side="SELL", quantity=11).status_code == 422
        assert Decimal(report(client)["positions"]["PETR4"]["quantity"]) == 10
        assert order(client, 4, side="SELL", quantity=10).status_code == 200
        assert report(client)["positions"] == {}


def test_concurrent_duplicate_cannot_fill_twice(tmp_path: Path) -> None:
    path = tmp_path / "oms.sqlite3"
    with TestClient(create_app(settings(path), clock=lambda: NOW)) as client:
        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(executor.map(lambda _: order(client, 1).status_code, range(12)))
        assert sorted(statuses) == [200] + [409] * 11
        assert Decimal(report(client)["cash_brl"]) == Decimal("98998.5")
    assert count(path, "paper_fills") == count(path, "paper_orders") == count(path, "webhook_receipts") == 1


def test_concurrent_distinct_orders_cannot_overdraw_cash(tmp_path: Path) -> None:
    path = tmp_path / "oms.sqlite3"
    with TestClient(create_app(settings(path, initial_cash_brl="1000"), clock=lambda: NOW)) as client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda key: order(client, key, quantity=60).status_code, [1, 2]))
        assert sorted(statuses) == [200, 422]
        assert Decimal(report(client)["cash_brl"]) == Decimal("399.1")
    assert count(path, "paper_fills") == 1
    assert count(path, "webhook_receipts") == 2


def test_restart_keeps_account_and_duplicate_history(tmp_path: Path) -> None:
    path = tmp_path / "oms.sqlite3"
    config = settings(path)
    with TestClient(create_app(config, clock=lambda: NOW)) as client:
        assert order(client, 1).status_code == 200
        before = report(client)
    with TestClient(create_app(config, clock=lambda: NOW)) as client:
        assert report(client) == before
        assert order(client, 1).status_code == 409
        assert order(client, 2, side="SELL").status_code == 200
    with pytest.raises(RuntimeError, match="immutable paper account"):
        with TestClient(create_app(settings(path, initial_cash_brl="200000"))):
            pass


def test_dynamic_kill_marker_blocks_orders_and_readiness_without_restart(tmp_path: Path) -> None:
    marker = tmp_path / "kill.flag"
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3", kill_switch_path=marker), clock=lambda: NOW)) as client:
        assert order(client, 1, quantity=10).status_code == 200
        marker.touch()
        assert report(client)["kill_switch"] is True
        assert client.get("/ready").status_code == 503
        assert order(client, 2, side="SELL", quantity=10).status_code == 503
        marker.unlink()
        assert report(client)["kill_switch"] is False
        assert client.get("/ready").status_code == 200
        assert order(client, 3, side="SELL", quantity=10).status_code == 200
        assert report(client)["positions"] == {}


def test_status_requires_secret_and_never_returns_it(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3"))) as client:
        assert client.get("/paper/status").status_code == 401
        assert client.get("/paper/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get("/paper/status", headers=AUTH)
        assert response.status_code == 200
        assert SECRET not in response.text
        assert "webhook_secret" not in response.text


@pytest.mark.parametrize("table", ["paper_account", "paper_fills"])
def test_account_seed_and_fills_are_append_only(tmp_path: Path, table: str) -> None:
    path = tmp_path / "oms.sqlite3"
    with TestClient(create_app(settings(path), clock=lambda: NOW)) as client:
        assert order(client, 1).status_code == 200
        with sqlite3.connect(path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"DELETE FROM {table}")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"UPDATE {table} SET id = id")


def test_fill_failure_rolls_back_risk_reservation_order_and_audit(tmp_path: Path) -> None:
    path = tmp_path / "oms.sqlite3"
    with TestClient(create_app(settings(path), clock=lambda: NOW), raise_server_exceptions=False) as client:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TRIGGER fail_fill BEFORE INSERT ON paper_fills BEGIN SELECT RAISE(ABORT, 'test disk failure'); END")
        assert order(client, 1).status_code == 500
        for table in ["paper_orders", "paper_fills", "webhook_receipts", "audit_events"]:
            assert count(path, table) == 0
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TRIGGER fail_fill")
        assert order(client, 1).status_code == 200


def test_legacy_unfilled_orders_are_visible_and_never_replayed(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    # An old OMS row is a notification, not proof of a simulated execution.
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE paper_orders (id INTEGER PRIMARY KEY, ticker TEXT)")
        connection.execute("INSERT INTO paper_orders VALUES (1, 'PETR4')")
    with TestClient(create_app(settings(path), clock=lambda: NOW)) as client:
        state = report(client)
        assert state["ledger_status"] == "legacy_orders_require_review"
        assert state["legacy_unfilled_order_count"] == 1
        assert state["fill_count"] == 0
        assert Decimal(state["cash_brl"]) == 100000
        assert state["positions"] == {}
        assert client.get("/ready").status_code == 503
        response = order(client, 2)
        assert response.status_code == 503
        assert "legacy paper orders" in response.json()["detail"]
    assert count(path, "paper_fills") == 0


@pytest.mark.parametrize("overrides, expected", [
    ({"max_position_notional_brl": "999"}, "position would exceed"),
    ({"max_gross_exposure_fraction": "0.005"}, "gross exposure"),
])
def test_portfolio_exposure_limits(tmp_path: Path, overrides: dict[str, object], expected: str) -> None:
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3", **overrides), clock=lambda: NOW)) as client:
        response = order(client, 1)
        assert response.status_code == 422
        assert expected in response.json()["detail"]
        assert report(client)["fill_count"] == 0


def test_position_count_limit_allows_held_position_sell(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "oms.sqlite3", max_positions=1), clock=lambda: NOW)) as client:
        assert order(client, 1).status_code == 200
        assert order(client, 2, ticker="VALE3").status_code == 422
        assert order(client, 3, side="SELL").status_code == 200
        assert order(client, 4, ticker="VALE3").status_code == 200


def test_config_resolves_dynamic_marker_and_keeps_decimal_fee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADINGVIEW_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("OMS_SIMULATION_CONFIG", raising=False)
    config = load_runtime_settings().oms
    assert config.kill_switch_path.is_absolute()
    assert config.cost_per_side == Decimal("0.0015")
    assert config.initial_cash_brl == Decimal("100000")


def test_placeholder_secret_is_rejected_even_when_long_enough(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unsafe placeholder"):
        RuntimeSettings(
            webhook_secret=SecretStr("replace-with-a-random-secret-at-least-32-characters"),
            oms=settings(tmp_path / "oms.sqlite3").oms,
        )


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("io failure")])
def test_kill_marker_filesystem_errors_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    config = settings(tmp_path / "oms.sqlite3", kill_switch_path=tmp_path / "kill.flag").oms

    def fail_stat(self: Path):
        raise error

    monkeypatch.setattr(Path, "lstat", fail_stat)
    assert kill_switch_active(config) is True


@pytest.mark.parametrize("field", ["initial_cash_brl", "cost_per_side", "max_position_notional_brl", "max_gross_exposure_fraction"])
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_accounting_config_is_rejected(tmp_path: Path, field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        settings(tmp_path / "oms.sqlite3", **{field: value})
