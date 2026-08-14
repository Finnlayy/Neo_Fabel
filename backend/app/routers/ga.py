"""Genetic forward optimizer API (/api/ga/*)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth import require_user
from backend.app.integrations.ga_optimizer.jobs import ga_jobs
from backend.app.integrations.ga_optimizer.pine_export import list_templates
from backend.app.integrations.ga_optimizer.schemas import ExportPineRequest, OptimizeRequest
from backend.app.settings import get_settings

router = APIRouter(tags=["ga"])


def _require_enabled() -> None:
    if not get_settings().ga_optimizer_enabled:
        raise HTTPException(
            status_code=503,
            detail={"code": "ga_disabled", "message": "GA_OPTIMIZER_ENABLED=false"},
        )


@router.post("/api/ga/optimize")
async def ga_optimize(
    payload: OptimizeRequest, _user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    _require_enabled()
    settings = get_settings()
    body = payload.model_dump()
    if body.get("population") is None:
        body["population"] = settings.ga_default_population
    if body.get("generations") is None:
        body["generations"] = settings.ga_default_generations
    try:
        return await ga_jobs.start_optimize(body)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"code": "ga_error", "message": str(exc)}) from exc


@router.get("/api/ga/runs/{run_id}")
async def ga_run_status(run_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_enabled()
    job = ga_jobs.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Unknown runId"})
    return {
        "runId": job.get("runId"),
        "status": job.get("status"),
        "progress": job.get("progress"),
        "top3": job.get("top3") or [],
        "error": job.get("error"),
        "createdAt": job.get("createdAt"),
        "updatedAt": job.get("updatedAt"),
        "settings": (job.get("results") or {}).get("settings") or (job.get("request") or {}),
    }


@router.get("/api/ga/runs")
async def ga_list_runs(
    limit: int = 20, _user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    _require_enabled()
    rows = ga_jobs.list_recent(limit=max(1, min(limit, 100)))
    return {
        "runs": [
            {
                "runId": r.get("runId"),
                "status": r.get("status"),
                "createdAt": r.get("createdAt"),
                "updatedAt": r.get("updatedAt"),
                "progress": r.get("progress"),
                "error": r.get("error"),
            }
            for r in rows
        ]
    }


@router.post("/api/ga/export-pine")
async def ga_export_pine(
    payload: ExportPineRequest, _user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    _require_enabled()
    try:
        return ga_jobs.export_pine(payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)}) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail={"code": "export_error", "message": str(exc)}) from exc


@router.get("/api/ga/templates")
async def ga_templates(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_enabled()
    return {"templates": list_templates()}
