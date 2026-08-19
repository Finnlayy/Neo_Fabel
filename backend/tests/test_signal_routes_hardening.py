"""MCP same-path submission, secret-free views, body/exponent/auth hardening."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from backend.app.settings import Settings
from backend.app.signals.auth import make_credential, verify_credential
from backend.app.signals.mcp_server import submit_trading_signal
from backend.app.signals.schemas import (
    McpSubmitArgs,
    SignalReceipt,
    SignalSubmissionView,
    TradingViewWebhookBody,
)
from backend.app.signals.service import SignalSubmissionService


def _paper_settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "kraken_live_trading_enabled": False,
        "kraken_autonomy_level": 2,
        "signal_routes_enabled": True,
        "tradingview_ingress_enabled": True,
        "mcp_signal_adapter_enabled": True,
        "signal_credential_pepper": "test-pepper",
        "signal_max_body_bytes": 256,
    }
    base.update(overrides)
    return Settings(**base)


def _mcp_args(**overrides) -> McpSubmitArgs:
    data = {
        "idempotency_key": "mcp-sig-1",
        "occurred_at": "2026-07-18T12:00:00Z",
        "strategy_id": "S",
        "pair": "ADAUSD",
        "side": "buy",
        "volume": "1",
        "order_type": "market",
    }
    data.update(overrides)
    return McpSubmitArgs.model_validate(data)


def test_signal_receipt_and_submission_view_omit_secrets():
    forbidden = {
        "credential",
        "plaintext",
        "digest",
        "secret",
        "bearer",
        "pepper",
        "authorization",
        "token",
    }
    receipt_fields = set(SignalReceipt.model_fields)
    submission_fields = set(SignalSubmissionView.model_fields)
    assert not (receipt_fields & forbidden)
    assert not (submission_fields & forbidden)

    receipt = SignalReceipt(submission_id=uuid4(), request_id="req-1")
    dumped = receipt.model_dump()
    assert "credential" not in dumped
    assert "plaintext" not in dumped
    blob = str(dumped).lower()
    assert "tvsec_" not in blob
    assert "mcptok_" not in blob

    view = SignalSubmissionView(
        id=str(uuid4()),
        route_id=str(uuid4()),
        source="mcp",
        signal_id="sig",
        pair="ADAUSD",
        side="buy",
        volume="1",
        order_type="market",
        mode_snapshot="advisory",
        status="queued",
        reason_code=None,
        request_id="req-1",
        paper_intent_id=None,
        occurred_at=datetime.now(UTC).isoformat(),
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )
    view_dump = view.model_dump()
    assert "plaintext" not in view_dump
    assert "digest" not in view_dump
    assert "credential" not in view_dump


def test_mcp_and_webhook_reject_exponent_literals():
    with pytest.raises(ValidationError):
        McpSubmitArgs.model_validate(
            {
                "idempotency_key": "k",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "ADAUSD",
                "side": "buy",
                "volume": "1e-3",
                "order_type": "market",
            }
        )
    with pytest.raises(ValidationError):
        TradingViewWebhookBody.model_validate(
            {
                "schema_version": 1,
                "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
                "signal_id": "x",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "ADAUSD",
                "side": "buy",
                "volume": "1E-2",
                "order_type": "market",
            }
        )
    with pytest.raises(ValidationError):
        McpSubmitArgs.model_validate(
            {
                "idempotency_key": "k",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "ADAUSD",
                "side": "buy",
                "volume": "1",
                "order_type": "limit",
                "price": "1e6",
            }
        )


def test_verify_credential_rejects_empty_plaintext():
    settings = _paper_settings()
    generated = make_credential("mcp_bearer", settings)
    assert not verify_credential(
        "",
        generated.digest,
        settings,
        revoked_at=None,
        expires_at=None,
    )


@pytest.mark.asyncio
async def test_mcp_submit_uses_same_service_accept_path():
    settings = _paper_settings()
    service = SignalSubmissionService(settings)
    route = SimpleNamespace(
        id=str(uuid4()),
        public_route_key="pk",
        strategy_id="S",
        mode="advisory",
        enabled=True,
        execution_target="kraken_paper",
        version=1,
        policy_version="v1",
        max_event_age_seconds=300,
    )
    cred = SimpleNamespace(id="c1", last_used_at=None)
    expected = SignalReceipt(submission_id=uuid4(), request_id="rid-mcp")

    with patch.object(service, "_resolve_mcp_bearer", new=AsyncMock(return_value=(cred, route))):
        with patch.object(service, "_accept", new=AsyncMock(return_value=expected)) as accept:
            receipt = await service.submit_mcp(
                AsyncMock(),
                bearer="mcptok_test_token_value_xxxx",
                args=_mcp_args(),
                request_id="rid-mcp",
            )

    assert receipt is expected
    accept.assert_awaited_once()
    kwargs = accept.await_args.kwargs
    assert kwargs["source"] == "mcp"
    assert kwargs["signal_id"] == "mcp-sig-1"
    assert kwargs["pair"] == "ADAUSD"
    assert kwargs["volume"] == Decimal(1)
    assert kwargs["credential"] is cred
    assert kwargs["route"] is route


@pytest.mark.asyncio
async def test_mcp_http_adapter_delegates_to_submit_mcp():
    settings = _paper_settings()
    expected = SignalReceipt(submission_id=uuid4(), request_id="from-adapter")
    args = _mcp_args()
    session = AsyncMock()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/mcp/signals/submit",
        "raw_path": b"/api/v1/mcp/signals/submit",
        "query_string": b"",
        "headers": [(b"content-length", b"120"), (b"authorization", b"Bearer mcptok_ok")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    request = Request(scope)

    with patch("backend.app.signals.mcp_server.get_settings", return_value=settings), patch.object(
        SignalSubmissionService,
        "submit_mcp",
        new=AsyncMock(return_value=expected),
    ) as submit_mcp:
        receipt = await submit_trading_signal(
            args,
            request,
            session=session,
            authorization="Bearer mcptok_ok",
        )

    assert receipt is expected
    submit_mcp.assert_awaited_once()
    call_kwargs = submit_mcp.await_args.kwargs
    assert call_kwargs["bearer"] == "mcptok_ok"
    assert call_kwargs["args"] is args


@pytest.mark.asyncio
async def test_mcp_rejects_oversized_content_length():
    settings = _paper_settings(signal_max_body_bytes=64)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/mcp/signals/submit",
        "raw_path": b"/api/v1/mcp/signals/submit",
        "query_string": b"",
        "headers": [(b"content-length", b"9999")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    request = Request(scope)
    with patch("backend.app.signals.mcp_server.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc:
            await submit_trading_signal(
                _mcp_args(),
                request,
                session=AsyncMock(),
                authorization="Bearer mcptok_ok",
            )
    assert exc.value.status_code == 413
    assert exc.value.detail["code"] == "body_too_large"


@pytest.mark.asyncio
async def test_tradingview_webhook_rejects_oversized_body():
    from backend.app.signals.router import tradingview_webhook

    settings = _paper_settings(signal_max_body_bytes=32)
    huge = b'{"schema_version":1,"credential":"' + (b"x" * 200) + b'"}'
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/webhooks/tradingview/pk",
        "raw_path": b"/api/v1/webhooks/tradingview/pk",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }

    async def receive():
        return {"type": "http.request", "body": huge, "more_body": False}

    request = Request(scope, receive)
    response = MagicMock()

    with patch("backend.app.signals.router.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc:
            await tradingview_webhook(
                "pk",
                request,
                response,
                session=AsyncMock(),
            )
    assert exc.value.status_code == 413
    assert exc.value.detail["code"] == "body_too_large"


@pytest.mark.asyncio
async def test_mcp_blank_bearer_auth_failed():
    settings = _paper_settings()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/mcp/signals/submit",
        "raw_path": b"/api/v1/mcp/signals/submit",
        "query_string": b"",
        "headers": [(b"content-length", b"40")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    request = Request(scope)
    with patch("backend.app.signals.mcp_server.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc:
            await submit_trading_signal(
                _mcp_args(),
                request,
                session=AsyncMock(),
                authorization="Bearer   ",
            )
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth_failed"
