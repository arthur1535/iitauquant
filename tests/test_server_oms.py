from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.server.app import create_app
from src.server.config import OmsSimulationConfig, RuntimeSettings, load_runtime_settings


FIXED_NOW = 1_800_000_000.0
TEST_SECRET = "test-webhook-secret-with-more-than-32-bytes"


def _settings(database_path: Path, *, kill_switch: bool = False) -> RuntimeSettings:
    return RuntimeSettings(
        webhook_secret=SecretStr(TEST_SECRET),
        oms=OmsSimulationConfig(
            mode="paper",
            database_path=database_path,
            allowed_symbols=frozenset({"PETR4", "VALE3"}),
            max_quantity_per_order=100,
            max_notional_brl_per_order=10_000,
            replay_window_seconds=300,
            future_tolerance_seconds=30,
            max_body_bytes=65_536,
            kill_switch=kill_switch,
        ),
    )


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "paper-oms.sqlite3"


@pytest.fixture
def client(database_path: Path):
    application = create_app(_settings(database_path), clock=lambda: FIXED_NOW)
    with TestClient(application) as test_client:
        yield test_client


def _payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy": "MOMENTUM_ATR",
        "action": "BUY",
        "order_type": "MARKET",
        "ticker": "PETR4",
        "close_price": 25.50,
        "stop_price": 23.10,
        "quantity": 10,
        "timestamp": int(FIXED_NOW * 1_000),
        "nonce": "nonce-00000001",
        "idempotency_key": "paper-event-00000001",
        "reason": "MOMENTUM_ENTRY",
        "metadata": {
            "exchange": "BMFBOVESPA",
            "interval": "1D",
            "bar_time": "2027-01-15T00:00:00Z",
        },
    }
    payload.update(updates)
    return payload


def _signed_request(
    client: TestClient,
    payload: dict[str, object],
    *,
    secret: str = TEST_SECRET,
    signature_override: str | None = None,
):
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook/tradingview",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature_override or f"sha256={signature}",
        },
    )


def _scalar(database_path: Path, query: str) -> object:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(query).fetchone()[0]


def test_valid_webhook_creates_only_a_paper_order(
    client: TestClient, database_path: Path
) -> None:
    response = _signed_request(client, _payload(ticker="BMFBOVESPA:PETR4"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "mode": "paper",
        "execution": "SIMULATED_ONLY",
        "paper_order_id": 1,
        "idempotency_key": "paper-event-00000001",
        "ticker": "PETR4",
        "action": "BUY",
        "notional_brl": "255.0",
        "paper_fill_id": 1,
        "fee_brl": "0.38250",
        "cash_after_brl": "99744.61750",
        "price_source": "ALERT_REFERENCE_SIMULATION",
    }
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 1
    assert _scalar(
        database_path,
        "SELECT execution_mode FROM paper_orders WHERE id = 1",
    ) == "paper"
    assert _scalar(database_path, "PRAGMA journal_mode") == "wal"


@pytest.mark.parametrize("signature", ["bad", "sha256=" + "0" * 64, None])
def test_invalid_or_missing_signature_returns_401(
    client: TestClient, database_path: Path, signature: str | None
) -> None:
    payload = _payload()
    if signature is None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        response = client.post(
            "/webhook/tradingview",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    else:
        response = _signed_request(client, payload, signature_override=signature)

    assert response.status_code == 401
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 0
    assert _scalar(
        database_path,
        "SELECT count(*) FROM audit_events WHERE outcome = 'authentication_failed'",
    ) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"close_price": 26, "nonce": "nonce-00000002"},
        {"close_price": 26, "idempotency_key": "paper-event-00000002"},
    ],
)
def test_same_idempotency_key_or_nonce_is_rejected_as_replay(
    client: TestClient,
    database_path: Path,
    updates: dict[str, object],
) -> None:
    assert _signed_request(client, _payload()).status_code == 200

    duplicate = _payload(**updates)
    response = _signed_request(client, duplicate)

    assert response.status_code == 409
    assert response.json()["detail"] == "duplicate or replayed webhook"
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 1
    assert _scalar(
        database_path,
        "SELECT count(*) FROM audit_events WHERE outcome = 'duplicate_or_replay'",
    ) == 1


@pytest.mark.parametrize(
    "timestamp",
    [
        int((FIXED_NOW - 301) * 1_000),
        int((FIXED_NOW + 31) * 1_000),
    ],
)
def test_timestamp_outside_replay_window_returns_409(
    client: TestClient, timestamp: int
) -> None:
    response = _signed_request(client, _payload(timestamp=timestamp))
    assert response.status_code == 409


def test_timezone_aware_iso_timestamp_is_accepted(client: TestClient) -> None:
    iso_timestamp = datetime.fromtimestamp(FIXED_NOW, timezone.utc).isoformat()
    response = _signed_request(client, _payload(timestamp=iso_timestamp))
    assert response.status_code == 200


def test_symbol_allowlist_is_enforced(client: TestClient, database_path: Path) -> None:
    response = _signed_request(client, _payload(ticker="MGLU3"))
    assert response.status_code == 403
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"quantity": 101},
        {"quantity": 100, "close_price": 100.01},
    ],
)
def test_quantity_and_notional_limits_are_enforced(
    client: TestClient, database_path: Path, updates: dict[str, object]
) -> None:
    response = _signed_request(client, _payload(**updates))
    assert response.status_code == 422
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 0


def test_kill_switch_blocks_orders_and_readiness(database_path: Path) -> None:
    application = create_app(_settings(database_path, kill_switch=True), clock=lambda: FIXED_NOW)
    with TestClient(application) as test_client:
        assert test_client.get("/health").status_code == 200
        ready = test_client.get("/ready")
        response = _signed_request(test_client, _payload())

    assert ready.status_code == 503
    assert ready.json()["kill_switch"] is True
    assert response.status_code == 503
    assert _scalar(database_path, "SELECT count(*) FROM paper_orders") == 0


def test_business_tables_are_append_only(
    client: TestClient, database_path: Path
) -> None:
    assert _signed_request(client, _payload()).status_code == 200
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE paper_orders SET ticker = 'VALE3' WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM audit_events")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE webhook_receipts SET nonce = 'hacked' WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM webhook_receipts WHERE id = 1")


@pytest.mark.parametrize("bad_ts", ["-1000", "2026-09-07T10:00:00", "not-a-timestamp"])
def test_invalid_or_naive_iso_timestamp_rejected(client: TestClient, bad_ts: str) -> None:
    response = _signed_request(client, _payload(timestamp=bad_ts))
    assert response.status_code in (409, 422)


def test_out_of_order_sell_before_buy_behavior(client: TestClient) -> None:
    sell_resp = _signed_request(
        client,
        _payload(
            action="SELL",
            reason="EXIT_STOP_TRIGGERED",
            nonce="nonce-sell-0001",
            idempotency_key="idemp-sell-0001",
        ),
    )
    assert sell_resp.status_code == 422
    assert "short sales are disabled" in sell_resp.json()["detail"]

    buy_resp = _signed_request(
        client,
        _payload(
            action="BUY",
            reason="MOMENTUM_ENTRY",
            nonce="nonce-buy-00001",
            idempotency_key="idemp-buy-00001",
        ),
    )
    assert buy_resp.status_code == 200


def test_secret_is_required_and_has_no_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("TRADINGVIEW_WEBHOOK_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="TRADINGVIEW_WEBHOOK_SECRET is required"):
        load_runtime_settings(config_path)
