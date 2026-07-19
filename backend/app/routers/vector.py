"""Phase 1 vector routes — Qdrant-backed (/api/v1/vector/*)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..integrations.qdrant_store import QdrantStoreError, get_qdrant_store
from ..schemas_vector import VectorSearchRequest, VectorUpsertRequest
from ..settings import get_settings

router = APIRouter(prefix="/api/v1/vector", tags=["vector"])


def _http_error(exc: QdrantStoreError) -> HTTPException:
    status = 503 if exc.retryable or exc.code in {"qdrant_upsert_failed", "qdrant_search_failed"} else 422
    if exc.code == "qdrant_disabled":
        status = 503
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@router.get("/health")
async def vector_health() -> dict[str, Any]:
    """Probe Qdrant readiness. Public (no auth) so the UI can choose backend mode."""
    settings = get_settings()
    store = get_qdrant_store()
    probe = await store.health()
    return {
        **probe,
        "feature": "phase1-qdrant",
        "backend": "qdrant" if probe.get("ready") else ("disabled" if not settings.qdrant_enabled else "unavailable"),
    }


@router.get("/ready")
async def vector_ready() -> dict[str, Any]:
    probe = await get_qdrant_store().health()
    if not probe.get("ready"):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "qdrant_unavailable",
                "message": probe.get("error") or "Qdrant is not ready",
                "enabled": probe.get("enabled"),
            },
        )
    return {"status": "ok", "ready": True, "collection": probe.get("collection")}


@router.post("/collections/ensure")
async def vector_ensure_collection() -> dict[str, Any]:
    try:
        result = await get_qdrant_store().ensure_collection()
    except QdrantStoreError as exc:
        raise _http_error(exc) from exc
    return {"success": True, **result}


@router.post("/points")
async def vector_upsert(payload: VectorUpsertRequest) -> dict[str, Any]:
    points = [point.model_dump() for point in payload.points]
    try:
        result = await get_qdrant_store().upsert_points(points)
    except QdrantStoreError as exc:
        raise _http_error(exc) from exc
    return {"success": True, **result}


@router.post("/search")
async def vector_search(payload: VectorSearchRequest) -> dict[str, Any]:
    if payload.metric != "cosine":
        raise HTTPException(
            status_code=422,
            detail={"code": "unsupported_metric", "message": "Phase 1 search supports cosine only"},
        )
    try:
        result = await get_qdrant_store().search(
            payload.vector,
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
        )
    except QdrantStoreError as exc:
        raise _http_error(exc) from exc
    return {"success": True, **result}


@router.get("/points")
async def vector_list_points(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    try:
        result = await get_qdrant_store().list_points(limit=limit)
    except QdrantStoreError as exc:
        raise _http_error(exc) from exc
    return {"success": True, **result}


@router.delete("/points/{document_id}")
async def vector_delete_point(document_id: str) -> dict[str, Any]:
    try:
        result = await get_qdrant_store().delete_point(document_id)
    except QdrantStoreError as exc:
        raise _http_error(exc) from exc
    return {"success": True, **result}
