"""Phase 2 market stream HTTP + WebSocket routes (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from ..market.stream import get_market_stream_hub
from ..settings import get_settings

router = APIRouter(tags=["market-stream"])


@router.get("/api/v1/market/stream/health")
async def market_stream_health() -> dict:
    settings = get_settings()
    hub = get_market_stream_hub()
    return {
        "status": "ok" if hub.enabled else "disabled",
        "backend": "websocket",
        "paper_only": not settings.trade_commands_enabled,
        **hub.health(),
    }


@router.websocket("/api/v1/market/stream")
async def market_stream(websocket: WebSocket) -> None:
    hub = get_market_stream_hub()
    if not hub.enabled:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "market_stream_disabled",
                "hint": "Set MARKET_STREAM_ENABLED=true",
            }
        )
        await websocket.close(code=1000)
        return
    await hub.serve(websocket)
