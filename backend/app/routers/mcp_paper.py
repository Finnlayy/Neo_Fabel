"""Fable MCP → LocalPaperLedger HTTP bridge (paper-only).

Datei: mcp_paper.py
Zweck: Empfaengt Fill-Events vom Rust fable-mcp und schreibt sie ins LocalPaperLedger.
Erstellt: 2026-07-21 | Version: 1.0
Abhaengig: paper_factory, settings, rationale
Sicherheit: Nur Paper — niemals Live-Kraken, kein Deposit/Withdraw.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.app.integrations.kraken_cli import KrakenCliError
from backend.app.integrations.paper_factory import build_paper_router
from backend.app.settings import get_settings
from backend.app.trading.feedback.rationale import rationale_from_fill_row

logger = logging.getLogger("neo_fabel.mcp_paper")

router = APIRouter(prefix="/api/v1/mcp/paper", tags=["mcp-paper-bridge"])


class McpPaperFillRequest(BaseModel):
    """Fill payload from Rust fable-mcp process_next_bar (paper only)."""

    event: Literal["entry", "stop_loss", "take_profit"] = "entry"
    side: Literal["buy", "sell"]
    pair: str = Field(default="ADAUSD", min_length=3, max_length=32)
    price: Decimal = Field(gt=0)
    volume: Decimal = Field(gt=0)
    pnl: Decimal | None = None
    rationale: str = Field(default="", max_length=180)
    market_type: Literal["spot", "futures"] = "spot"
    source: str = Field(default="fable-mcp", max_length=64)

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        return value.strip().upper().replace("/", "").replace("-", "")

    @field_validator("rationale")
    @classmethod
    def truncate_rationale(cls, value: str) -> str:
        return (value or "").strip()[:180]


class McpPaperFillResponse(BaseModel):
    ok: bool
    mode: Literal["paper"] = "paper"
    request_id: str
    rationale: str
    result: dict[str, Any]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid4())


def _assert_bridge_auth(authorization: str | None) -> None:
    settings = get_settings()
    if not settings.fable_mcp_bridge_enabled:
        raise HTTPException(
            status_code=503,
            detail={"code": "bridge_disabled", "message": "FABLE_MCP_BRIDGE_ENABLED is false"},
        )
    expected = (settings.fable_mcp_bridge_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "bridge_token_required",
                "message": "FABLE_MCP_BRIDGE_TOKEN must be set when the MCP paper bridge is enabled",
            },
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token.strip() != expected:
        raise HTTPException(
            status_code=401,
            detail={"code": "bridge_auth_failed", "message": "Bearer token required for MCP paper bridge"},
        )


def _trade_side_for_ledger(event: str, position_side: str) -> Literal["buy", "sell"]:
    """Map engine position side + event to LocalPaperLedger trade side."""
    if event == "entry":
        return "buy" if position_side == "buy" else "sell"
    # Exit: close the position with the opposite trade.
    return "sell" if position_side == "buy" else "buy"


@router.post("/fill", response_model=McpPaperFillResponse)
async def mcp_paper_fill(
    payload: McpPaperFillRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> McpPaperFillResponse:
    """Apply a paper fill from fable-mcp into LocalPaperLedger. Never places live orders."""
    rid = _request_id(request)
    _assert_bridge_auth(authorization)

    settings = get_settings()
    # Auth helper already requires enabled + non-empty token.
    trade_side = _trade_side_for_ledger(payload.event, payload.side)
    rationale = payload.rationale or rationale_from_fill_row(
        {
            "pair": payload.pair,
            "side": trade_side,
            "price": str(payload.price),
            "pnl": str(payload.pnl) if payload.pnl is not None else None,
            "rationale": payload.rationale,
        }
    )
    rationale = rationale[:180]
    logger.info(
        "mcp_paper_fill event=%s side=%s trade=%s pair=%s vol=%s px=%s rationale=%s rid=%s",
        payload.event,
        payload.side,
        trade_side,
        payload.pair,
        payload.volume,
        payload.price,
        rationale,
        rid,
    )

    sink = build_paper_router(settings)
    try:
        raw = await sink.paper_order(
            trade_side,
            payload.pair,
            payload.volume,
            "market",
            payload.price,
            market_type=payload.market_type,
            leverage=1,
            rationale=rationale,
        )
    except (KrakenCliError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "paper_fill_failed", "message": str(exc), "request_id": rid},
        ) from exc

    # Attach rationale onto the order/fill row when present; keep ledger source intact.
    if isinstance(raw, dict):
        order = raw.get("order")
        if isinstance(order, dict) and "rationale" not in order:
            order["rationale"] = rationale
        raw = {
            **raw,
            "rationale": rationale,
            "mcp_event": payload.event,
            "mcp_source": payload.source,
        }

    try:
        from backend.app.integrations.telegram_trade_notify import notify_trade_signal

        await notify_trade_signal(
            settings,
            kind="mcp_fill",
            pair=payload.pair,
            side=trade_side,
            volume=str(payload.volume),
            order_type="market",
            price=str(payload.price),
            source=payload.source or "fable_mcp",
            request_id=rid,
            extra=rationale,
            channel="MCP PAPER FILL",
        )
    except Exception:
        logger.debug("mcp paper fill telegram notify failed", exc_info=True)

    return McpPaperFillResponse(ok=True, request_id=rid, rationale=rationale, result=raw if isinstance(raw, dict) else {"raw": raw})
