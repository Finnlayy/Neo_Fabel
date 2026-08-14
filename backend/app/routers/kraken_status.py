"""Kraken status catalog endpoints — durable safety memory for live trading."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth import require_trading_admin, require_user
from backend.app.integrations.kraken_status import (
    assert_safe_to_trade_pair,
    load_catalog,
    load_index,
    refresh_from_statuspage,
)
from backend.app.trading.guardrails import GuardrailViolation

router = APIRouter(prefix="/api/v1/kraken/status", tags=["kraken-status"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "unknown"


@router.get("")
async def get_kraken_status(
    request: Request,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Return page indicator + non-operational components + incidents (index)."""
    rid = _request_id(request)
    index = load_index()
    if not index:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "status_catalog_missing",
                "message": "status catalog not loaded — POST /api/v1/kraken/status/refresh",
                "request_id": rid,
            },
        )
    return {
        "fetched_at": index.get("fetched_at"),
        "indicator": index.get("indicator"),
        "description": index.get("description"),
        "non_operational": index.get("non_operational") or [],
        "incidents": index.get("incidents") or [],
        "component_count": len(index.get("by_name") or {}),
        "status_page": "https://status.kraken.com",
        "request_id": rid,
    }


@router.get("/components")
async def get_kraken_status_components(
    request: Request,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Full expanded component list from durable memory."""
    rid = _request_id(request)
    catalog = load_catalog()
    if not catalog:
        raise HTTPException(
            status_code=503,
            detail={"code": "status_catalog_missing", "message": "catalog missing", "request_id": rid},
        )
    return {
        "fetched_at": catalog.get("fetched_at"),
        "source": catalog.get("source"),
        "page_status": catalog.get("page_status"),
        "component_count": catalog.get("component_count"),
        "non_operational": catalog.get("non_operational") or [],
        "incidents": catalog.get("incidents") or [],
        "components": catalog.get("components") or [],
        "safe_trading_policy": catalog.get("safe_trading_policy"),
        "request_id": rid,
    }


@router.post("/refresh")
async def refresh_kraken_status(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin),
) -> dict[str, Any]:
    """Pull latest summary.json from status.kraken.com into server memory."""
    rid = _request_id(request)
    try:
        catalog = await refresh_from_statuspage()
    except Exception as exc:  # noqa: BLE001 — surface upstream failures
        raise HTTPException(
            status_code=502,
            detail={"code": "status_refresh_failed", "message": str(exc), "request_id": rid},
        ) from exc
    return {
        "ok": True,
        "fetched_at": catalog.get("fetched_at"),
        "indicator": (catalog.get("page_status") or {}).get("indicator"),
        "description": (catalog.get("page_status") or {}).get("description"),
        "component_count": catalog.get("component_count"),
        "non_operational": catalog.get("non_operational") or [],
        "incidents": catalog.get("incidents") or [],
        "request_id": rid,
    }


@router.get("/check/{pair}")
async def check_pair_status(
    pair: str,
    request: Request,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Gate probe: is this pair safe per status memory?"""
    rid = _request_id(request)
    try:
        assert_safe_to_trade_pair(pair)
    except GuardrailViolation as exc:
        return {
            "ok": False,
            "pair": pair.upper(),
            "code": exc.code,
            "message": str(exc),
            "request_id": rid,
        }
    return {"ok": True, "pair": pair.upper(), "request_id": rid}
