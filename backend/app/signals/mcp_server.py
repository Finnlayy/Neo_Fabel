"""Authenticated MCP transport exposing only submit_trading_signal."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..settings import get_settings
from .schemas import McpSubmitArgs, SignalReceipt
from .service import SignalSubmissionService

mcp_router = APIRouter(tags=["signal-mcp"])


@mcp_router.post("/api/v1/mcp/signals/submit", response_model=SignalReceipt, status_code=202)
async def submit_trading_signal(
    args: McpSubmitArgs,
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> SignalReceipt:
    """Route-scoped MCP adapter tool. Mode/target/AI cannot be selected here."""
    settings = get_settings()
    if not settings.mcp_signal_adapter_enabled:
        raise HTTPException(status_code=503, detail={"code": "mcp_disabled", "message": "MCP adapter disabled"})
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail={"code": "auth_failed", "message": "authentication failed"})
    # Reject admin-like fields if a client smuggles them via raw JSON (extra=forbid on args).
    request_id = str(uuid4())
    service = SignalSubmissionService(settings)
    return await service.submit_mcp(session, bearer=token, args=args, request_id=request_id)


def mcp_tool_descriptor() -> dict:
    return {
        "name": "submit_trading_signal",
        "description": "Submit a canonical trading signal for paper processing. Route is bound from the bearer credential.",
        "inputSchema": McpSubmitArgs.model_json_schema(),
    }
