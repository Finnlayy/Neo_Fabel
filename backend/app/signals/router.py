"""TradingView ingress and Firebase-protected admin APIs."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_signal_admin, require_signal_admin_recent
from ..database import get_session
from ..settings import get_settings
from .schemas import (
    SignalAutomationStatus,
    SignalReceipt,
    SignalRouteCreate,
    SignalRoutePatch,
    SignalRouteView,
    SignalSubmissionView,
    TradingViewWebhookBody,
)
from .service import SignalSubmissionService

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
        payload = TradingViewWebhookBody.model_validate_json(body_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_payload", "message": "invalid payload"}) from exc

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
