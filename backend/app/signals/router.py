"""TradingView ingress and Firebase-protected admin APIs."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_signal_admin, require_signal_admin_recent, require_user
from ..database import get_session
from ..settings import get_settings
from .rna_context import get_rna_context, set_rna_context
from .schemas import (
    RnaContextUpdate,
    SignalAutomationStatus,
    SignalReceipt,
    SignalRouteCreate,
    SignalRoutePatch,
    SignalRouteView,
    SignalSubmissionView,
)
from .service import SignalSubmissionService
from .tv_webhook_parser import TvWebhookParseError, parse_tradingview_natural_webhook, to_kraken_order_payload

router = APIRouter(tags=["signal-routes"])


def _server_request_id(request: Request) -> tuple[str, str | None]:
    """Always mint a server UUID; bound inbound X-Request-ID as correlation only."""
    server_id = str(uuid4())
    inbound = request.headers.get("x-request-id")
    correlation = None
    if inbound and len(inbound) <= 64 and all(32 <= ord(ch) < 127 for ch in inbound):
        correlation = inbound
    return server_id, correlation


def _service() -> SignalSubmissionService:
    return SignalSubmissionService(get_settings())


@router.get("/api/v1/signal-automation/status", response_model=SignalAutomationStatus)
async def automation_status(
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> SignalAutomationStatus:
    _ = user
    return await _service().status(session)


@router.get("/api/v1/signal-routes", response_model=list[SignalRouteView])
async def list_routes(
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> list[SignalRouteView]:
    return await _service().list_routes(session, str(user.get("uid", "")))


@router.post("/api/v1/signal-routes", response_model=SignalRouteView, status_code=201)
async def create_route(
    payload: SignalRouteCreate,
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> SignalRouteView:
    return await _service().create_route(session, str(user.get("uid", "")), payload)


@router.get("/api/v1/signal-routes/{route_id}", response_model=SignalRouteView)
async def get_route(
    route_id: str,
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> SignalRouteView:
    return await _service().get_route(session, str(user.get("uid", "")), route_id)


@router.patch("/api/v1/signal-routes/{route_id}", response_model=SignalRouteView)
async def patch_route(
    route_id: str,
    payload: SignalRoutePatch,
    request: Request,
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> SignalRouteView:
    recent = False
    if payload.mode == "bypass_ai":
        await require_signal_admin_recent(request)
        recent = True
    return await _service().patch_route(
        session,
        str(user.get("uid", "")),
        route_id,
        payload,
        recent_auth=recent,
    )


@router.post("/api/v1/signal-routes/{route_id}/credentials/tradingview/rotate")
async def rotate_tv(
    route_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await require_signal_admin_recent(request)
    return await _service().rotate_credential(
        session, str(user.get("uid", "")), route_id, "tradingview_secret"
    )


@router.post("/api/v1/signal-routes/{route_id}/credentials/mcp/rotate")
async def rotate_mcp(
    route_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await require_signal_admin_recent(request)
    return await _service().rotate_credential(
        session, str(user.get("uid", "")), route_id, "mcp_bearer"
    )


@router.post("/api/v1/signal-routes/{route_id}/credentials/{credential_id}/revoke")
async def revoke_credential(
    route_id: str,
    credential_id: str,
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
):
    return await _service().revoke_credential(
        session, str(user.get("uid", "")), route_id, credential_id
    )


@router.get("/api/v1/signal-submissions", response_model=list[SignalSubmissionView])
async def list_submissions(
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
    route_id: str | None = None,
    source: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> list[SignalSubmissionView]:
    return await _service().list_submissions(
        session,
        str(user.get("uid", "")),
        route_id=route_id,
        source=source,
        status=status,
        cursor=cursor,
        limit=limit,
    )


@router.get("/api/v1/signal-submissions/{submission_id}", response_model=SignalSubmissionView)
async def get_submission(
    submission_id: str,
    user: dict = Depends(require_signal_admin),
    session: AsyncSession = Depends(get_session),
) -> SignalSubmissionView:
    return await _service().get_submission(session, str(user.get("uid", "")), submission_id)


@router.get("/api/v1/signals/engine/status")
async def fable_engine_status(
    user: dict = Depends(require_signal_admin),
) -> dict:
    """Read-only FableEngine status (start/stop only via env flags + restart)."""
    _ = user
    from .engine.generator import get_fable_engine
    from .engine.market_source import resolve_source

    settings = get_settings()
    engine = get_fable_engine()
    if engine is None:
        return {
            "enabled": settings.fable_engine_enabled,
            "dry_run": settings.fable_engine_dry_run,
            "started": False,
            "poll_seconds": settings.fable_engine_poll_seconds,
            "market_rpm": settings.fable_engine_market_rpm,
            "onnx_bias": settings.fable_engine_onnx_bias,
            "strategy_count": 0,
            "ticks": 0,
            "last_tick_at": None,
            "last_error": None,
            "dry_run_count": 0,
            "candle_source": resolve_source(settings),
            "interval": settings.fable_engine_interval,
            "note": "engine not running — set FABLE_ENGINE_ENABLED=true and restart the API",
        }
    payload = engine.status()
    payload["candle_source"] = resolve_source(settings)
    payload["interval"] = settings.fable_engine_interval
    return payload


@router.get("/api/v1/signals/engine/dryruns")
async def fable_engine_dryruns(
    user: dict = Depends(require_signal_admin),
    limit: int = 50,
) -> list[dict]:
    """Most recent dry-run records (in-memory ring buffer; newest last)."""
    _ = user
    from .engine.generator import get_fable_engine

    engine = get_fable_engine()
    if engine is None:
        return []
    return engine.recent_dry_runs(limit=min(max(limit, 1), 200))


@router.post("/api/v1/signals/tv-parse-preview")
async def tradingview_parse_preview(
    request: Request,
    _user: dict = Depends(require_signal_admin),
) -> dict:
    """Dry-run: natural TV JSON → Neo body + Kraken order fields (no route submit)."""
    settings = get_settings()
    body_bytes = await request.body()
    if len(body_bytes) > settings.signal_max_body_bytes:
        raise HTTPException(status_code=413, detail={"code": "body_too_large", "message": "payload too large"})
    try:
        raw = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_json", "message": "invalid JSON"}) from exc
    try:
        payload = parse_tradingview_natural_webhook(raw if isinstance(raw, dict) else {})
    except TvWebhookParseError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    return {
        "ok": True,
        "neo": payload.model_dump(mode="json"),
        "kraken_order": to_kraken_order_payload(payload),
    }


@router.post(
    "/api/v1/webhooks/tradingview/{public_route_key}",
    response_model=SignalReceipt,
    status_code=202,
)
async def tradingview_webhook(
    public_route_key: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SignalReceipt:
    settings = get_settings()
    body_bytes = await request.body()
    if len(body_bytes) > settings.signal_max_body_bytes:
        raise HTTPException(status_code=413, detail={"code": "body_too_large", "message": "payload too large"})
    try:
        raw = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_json", "message": "body must be UTF-8 JSON"},
        ) from exc
    try:
        payload = parse_tradingview_natural_webhook(raw if isinstance(raw, dict) else {})
    except TvWebhookParseError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc), "kraken_hint": "fix TV JSON / placeholders"},
        ) from exc

    # Attach Kraken-normalized order preview for operators (response header only).
    kraken = to_kraken_order_payload(payload)
    response.headers["X-Kraken-Pair"] = kraken["pair"] or ""
    response.headers["X-Kraken-Side"] = kraken["side"] or ""
    response.headers["X-Kraken-Volume"] = kraken["volume"] or ""

    request_id, correlation = _server_request_id(request)
    response.headers["X-Request-ID"] = request_id
    if correlation:
        response.headers["X-External-Correlation-ID"] = correlation

    receipt = await _service().submit_tradingview(
        session,
        public_route_key=public_route_key,
        body=payload,
        request_id=request_id,
        external_correlation_id=correlation,
    )
    return receipt


@router.put("/api/v1/signals/rna-context")
async def update_rna_context(
    payload: RnaContextUpdate,
    _user: dict = Depends(require_user),
) -> dict:
    """Publish latest RNA blind-pattern bias for Fable Engine signal intake."""
    ctx = set_rna_context(bias=payload.bias, confidence=payload.confidence, symbol=payload.symbol)
    return {
        "ok": True,
        "bias": ctx.bias,
        "confidence": str(ctx.confidence),
        "symbol": ctx.symbol,
        "updated_at": ctx.updated_at,
    }


@router.get("/api/v1/signals/rna-context")
async def read_rna_context(_user: dict = Depends(require_user)) -> dict:
    ctx = get_rna_context()
    if ctx is None:
        return {"ok": True, "context": None}
    return {
        "ok": True,
        "context": {
            "bias": ctx.bias,
            "confidence": str(ctx.confidence),
            "symbol": ctx.symbol,
            "updated_at": ctx.updated_at,
        },
    }
