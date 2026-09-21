"""FastAPI application for authenticated TradingView paper orders."""

from __future__ import annotations

import json
import hmac
import logging
import time
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import AsyncIterator, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import RuntimeSettings, load_runtime_settings
from .models import PaperOrderResponse, TradingViewAlert
from .oms import kill_switch_active
from .security import (
    parse_event_timestamp_ms,
    request_sha256,
    timestamp_within_window,
    verify_signature,
)
from .storage import AuditStore


logger = logging.getLogger("iitauquant.paper_oms")


def _validation_details(exc: ValidationError) -> list[dict[str, object]]:
    # ValidationError.json safely serializes ValueError contexts and omits user input.
    return json.loads(exc.json(include_input=False, include_url=False))


async def _read_body_with_limit(request: Request, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail="request body is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(
    runtime_settings: RuntimeSettings | None = None,
    *,
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    """Create the paper-only application.

    Configuration is loaded during lifespan startup so importing the ASGI module
    never substitutes a development secret.  Startup fails if the required secret
    is unavailable.
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        settings = runtime_settings or load_runtime_settings()
        if settings.oms.mode != "paper":  # Defensive even though Pydantic uses Literal.
            raise RuntimeError("only paper mode is supported")
        store = AuditStore(settings.oms.database_path)
        await run_in_threadpool(store.initialize, settings.oms.initial_cash_brl)
        application.state.runtime_settings = settings
        application.state.audit_store = store
        application.state.ready = True
        try:
            yield
        finally:
            application.state.ready = False

    application = FastAPI(
        title="Itaú Quant TradingView Paper OMS",
        version="1.0.0",
        description="Authenticated webhook receiver with simulation-only order persistence.",
        lifespan=lifespan,
    )
    application.state.ready = False

    @application.get("/health")
    @application.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, object]:
        return {
            "status": "alive",
            "mode": "paper",
            "live_broker_enabled": False,
        }

    @application.get("/ready")
    @application.get("/readyz", include_in_schema=False)
    async def readiness(request: Request) -> JSONResponse:
        if not request.app.state.ready:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "mode": "paper"},
            )
        settings: RuntimeSettings = request.app.state.runtime_settings
        store: AuditStore = request.app.state.audit_store
        database_ready = await run_in_threadpool(store.ping)
        killed = kill_switch_active(settings.oms)
        ledger_ready = False
        if database_ready:
            snapshot = await run_in_threadpool(store.paper_status)
            ledger_ready = snapshot.legacy_unfilled_order_count == 0
        ready = database_ready and ledger_ready and not killed
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "mode": "paper",
                "database": "ok" if database_ready else "unavailable",
                "kill_switch": killed,
                "ledger": "ready" if ledger_ready else "review_required",
            },
        )

    @application.get("/paper/status")
    async def paper_status(request: Request) -> JSONResponse:
        """Authenticated, read-only accounting at last alert fill reference prices."""
        settings: RuntimeSettings = request.app.state.runtime_settings
        expected = f"Bearer {settings.webhook_secret.get_secret_value()}".encode("utf-8")
        supplied = request.headers.get("Authorization", "").encode("utf-8")
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="invalid paper status credentials", headers={"WWW-Authenticate": "Bearer"})
        store: AuditStore = request.app.state.audit_store
        snapshot = await run_in_threadpool(store.paper_status)
        content = snapshot.as_dict()
        content["kill_switch"] = kill_switch_active(settings.oms)
        content["live_broker_enabled"] = False
        return JSONResponse(content=content, headers={"Cache-Control": "no-store"})

    @application.post(
        "/webhook/tradingview",
        response_model=PaperOrderResponse,
        status_code=200,
    )
    async def receive_tradingview_webhook(request: Request) -> PaperOrderResponse:
        settings: RuntimeSettings = request.app.state.runtime_settings
        store: AuditStore = request.app.state.audit_store

        try:
            body = await _read_body_with_limit(request, settings.oms.max_body_bytes)
        except HTTPException:
            # No full body exists, so use the hash of an empty sentinel and avoid
            # persisting attacker-controlled content.
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=request_sha256(b"oversized-request"),
                outcome="body_too_large",
                http_status=413,
            )
            raise

        body_hash = request_sha256(body)
        signature = request.headers.get("X-Webhook-Signature")
        secret_bytes = settings.webhook_secret.get_secret_value().encode("utf-8")
        if not verify_signature(body, signature, secret_bytes):
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=body_hash,
                outcome="authentication_failed",
                http_status=401,
            )
            logger.warning("Webhook authentication failed request_sha256=%s", body_hash)
            raise HTTPException(status_code=401, detail="invalid webhook signature")

        try:
            decoded = json.loads(body)
            payload = TradingViewAlert.model_validate(decoded)
        except (JSONDecodeError, UnicodeDecodeError):
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=body_hash,
                outcome="invalid_json",
                http_status=422,
            )
            raise HTTPException(
                status_code=422,
                detail="request body must be valid JSON",
            ) from None
        except ValidationError as exc:
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=body_hash,
                outcome="schema_rejected",
                http_status=422,
            )
            return JSONResponse(status_code=422, content={"detail": _validation_details(exc)})

        try:
            event_timestamp_ms = parse_event_timestamp_ms(payload.timestamp)
        except ValueError as exc:
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=body_hash,
                outcome="timestamp_rejected",
                http_status=409,
                payload=payload,
                details={"detail": str(exc)},
            )
            raise HTTPException(status_code=409, detail=str(exc)) from None

        if not timestamp_within_window(
            event_timestamp_ms,
            clock(),
            settings.oms.replay_window_seconds,
            settings.oms.future_tolerance_seconds,
        ):
            await run_in_threadpool(
                store.append_audit_event,
                request_hash=body_hash,
                outcome="replay_window_rejected",
                http_status=409,
                payload=payload,
                details={"detail": "timestamp is outside the accepted replay window"},
            )
            raise HTTPException(
                status_code=409,
                detail="timestamp is outside the accepted replay window",
            )

        result = await run_in_threadpool(
            store.record_authenticated_decision,
            payload=payload,
            event_timestamp_ms=event_timestamp_ms,
            request_hash=body_hash,
            config=settings.oms,
        )
        if result.duplicate:
            raise HTTPException(status_code=409, detail="duplicate or replayed webhook")
        if not result.accepted:
            raise HTTPException(status_code=result.http_status, detail=result.detail)

        assert result.paper_order_id is not None
        assert result.paper_fill_id is not None
        logger.info(
            "Paper order accepted id=%s ticker=%s action=%s request_sha256=%s",
            result.paper_order_id,
            payload.ticker,
            payload.action.value,
            body_hash,
        )
        return PaperOrderResponse(
            paper_order_id=result.paper_order_id,
            idempotency_key=payload.idempotency_key,
            ticker=payload.ticker,
            action=payload.action,
            notional_brl=str(result.notional_brl),
            paper_fill_id=result.paper_fill_id,
            fee_brl=str(result.fee_brl),
            cash_after_brl=str(result.cash_after_brl),
        )

    return application


app = create_app()
