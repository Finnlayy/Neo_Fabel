"""tvremix MCP surface for Pine search/read/errors/sweep + ledger diff."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth import require_user
from backend.app.integrations.pine_ledger import diff_against_ledger, load_ledger, upsert_script_snapshot
from backend.app.integrations.tvremix_client import TvremixClient, TvremixError
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/tvremix", tags=["tvremix"])


def _client() -> TvremixClient:
    return TvremixClient(get_settings())


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=30, ge=1, le=100)


class ReadLinesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_id: str = Field(min_length=1, max_length=256)
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=120, ge=1)
    name: str | None = Field(default=None, max_length=256)


class ErrorsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_id: str | None = Field(default=None, max_length=256)
    source: str | None = Field(default=None, max_length=500_000)


class MtfBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=2, max_length=64)
    intervals: list[str] | None = None


class LedgerSnapshotBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=256)
    read: bool = True


@router.get("/status")
async def tvremix_status(_user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    client = _client()
    tools: list[str] = []
    error = None
    if client.configured:
        try:
            tools = await client.list_tools()
        except TvremixError as exc:
            error = str(exc)
    return {
        "configured": client.configured,
        "enabled": settings.tvremix_enabled,
        "mcp_url": settings.tvremix_mcp_url,
        "tool_count": len(tools),
        "tools": tools[:80],
        "error": error,
        "ledger_scripts": len(load_ledger().get("scripts") or {}),
    }


@router.get("/scripts")
async def list_scripts(_user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        scripts = await client.list_pine_scripts()
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc
    return {"count": len(scripts), "scripts": scripts}


@router.post("/search")
async def search_scripts(payload: SearchBody, _user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        hits = await client.search_pine_scripts(payload.query, limit=payload.limit)
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc
    return {"query": payload.query, "count": len(hits), "hits": hits}


@router.post("/read-lines")
async def read_lines(payload: ReadLinesBody, _user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        return await client.read_pine_lines(
            payload.script_id,
            start_line=payload.start_line,
            end_line=payload.end_line,
            name=payload.name,
        )
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc


@router.post("/errors")
async def pine_errors(payload: ErrorsBody, _user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    return await client.get_pine_errors(payload.script_id, source=payload.source)


@router.post("/strategy-report")
async def strategy_report(
    payload: dict[str, Any] = Body(default_factory=dict),
    _user: dict = Depends(require_user),
) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        return await client.get_strategy_report(**payload)
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc


@router.post("/strategy-sweep")
async def strategy_sweep(
    payload: dict[str, Any] = Body(default_factory=dict),
    _user: dict = Depends(require_user),
) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        return await client.strategy_sweep(**payload)
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc


@router.post("/mtf")
async def multi_timeframe(payload: MtfBody, _user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    try:
        return await client.analyze_multi_timeframe(payload.symbol, intervals=payload.intervals)
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc


@router.get("/ledger")
async def get_ledger(_user: dict = Depends(require_user)) -> dict[str, Any]:
    return load_ledger()


@router.post("/ledger/snapshot")
async def ledger_snapshot(payload: LedgerSnapshotBody, _user: dict = Depends(require_user)) -> dict[str, Any]:
    client = _client()
    if not client.configured:
        raise HTTPException(status_code=503, detail={"code": "tvremix_unconfigured", "message": "TVREMIX_API_KEY missing"})
    if not payload.read:
        raise HTTPException(status_code=422, detail={"code": "read_required", "message": "read=true required"})
    try:
        read = await client.read_pine_script(payload.script_id, name=payload.name)
    except TvremixError as exc:
        raise HTTPException(status_code=502, detail={"code": "tvremix_error", "message": str(exc)}) from exc
    source = str(read.get("source") or "")
    before = diff_against_ledger(payload.script_id, source)
    entry = upsert_script_snapshot(
        script_id=payload.script_id,
        name=str(payload.name or read.get("name") or payload.script_id),
        source=source,
    )
    return {"diff_before_write": before, "entry": entry}
