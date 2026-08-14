"""ONNX model list / file / train / infer — paper research only."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.auth import require_user
from backend.app.integrations.backtest.ema_grid import synthetic_candles
from backend.app.integrations.onnx.dataset import FEATURE_SET
from backend.app.integrations.onnx.manifest import get_active, get_model_meta, list_models, set_active
from backend.app.integrations.onnx.paths import model_path
from backend.app.integrations.onnx.runtime import ensure_seed_models, netron_static_dir, onnx_deps_available
from backend.app.integrations.onnx.upload import MAX_UPLOAD_BYTES

router = APIRouter(prefix="/api/v1/onnx", tags=["onnx"])

_MODEL_ID_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
_JOBS: dict[str, dict[str, Any]] = {}


class InferRequest(BaseModel):
    model_id: str | None = None
    symbol: str = "BTCUSD"
    timeframe: str = "1h"
    asset_class: str = "crypto"
    allow_fallback: bool = False


class TrainRequest(BaseModel):
    model_id: str = "model4"
    symbol: str = "BTCUSD"
    timeframe: str = "1h"
    asset_class: str = "crypto"
    limit: int = Field(default=400, ge=50, le=5000)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class ActiveModelRequest(BaseModel):
    model_id: str


def _safe_model_id(model_id: str) -> str:
    mid = model_id.replace(".onnx", "").strip()
    if not _MODEL_ID_RE.match(mid):
        raise HTTPException(status_code=400, detail={"code": "invalid_model_id", "message": "bad model_id"})
    return mid


def _require_runtime() -> None:
    if not onnx_deps_available():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "onnx_deps_missing",
                "message": "Install optional deps: pip install -e \".[onnx]\"",
            },
        )


@router.get("/status")
async def onnx_status(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    available = onnx_deps_available()
    count = 0
    active = None
    if available:
        ensure_seed_models()
        count = len(list_models())
        active = get_active()
    return {
        "configured": available,
        "runtime_available": available,
        "netron_available": netron_static_dir() is not None,
        "models_dir": str(model_path("model4").parent),
        "model_count": count,
        "static_models_prefix": "/static/onnx",
        "active_model_id": active,
        "feature_set": FEATURE_SET,
    }


@router.get("/models")
async def onnx_models(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    if onnx_deps_available():
        ensure_seed_models()
        return {"models": list_models(), "active_model_id": get_active()}
    return {"models": [], "active_model_id": None}


@router.get("/models/active")
async def onnx_get_active(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_runtime()
    ensure_seed_models()
    mid = get_active()
    meta = get_model_meta(mid)
    return {"active_model_id": mid, "meta": meta}


@router.post("/models/active")
async def onnx_set_active(body: ActiveModelRequest, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_runtime()
    ensure_seed_models()
    mid = _safe_model_id(body.model_id)
    try:
        active = set_active(mid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": mid}) from None
    return {"active_model_id": active, "meta": get_model_meta(active)}


@router.post("/models/upload")
async def onnx_upload(
    file: UploadFile = File(...),
    model_id: str | None = Form(default=None),
    make_active: bool = Form(default=False),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Upload a .onnx file into the paper research registry (validated with onnx.checker)."""
    _require_runtime()
    ensure_seed_models()
    from backend.app.integrations.onnx.upload import save_uploaded_onnx

    name = file.filename or "model.onnx"
    if not name.lower().endswith(".onnx"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_extension", "message": "filename must end with .onnx"},
        )
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "too_large", "message": f"max {MAX_UPLOAD_BYTES} bytes"},
        )
    try:
        meta = save_uploaded_onnx(
            data=data,
            filename=name,
            model_id=model_id,
            make_active=make_active,
            source="upload",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_onnx", "message": str(exc)}) from exc
    return {"status": "uploaded", "meta": meta, "active_model_id": get_active()}


@router.get("/models/{model_id}/meta")
async def onnx_model_meta(model_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_runtime()
    ensure_seed_models()
    mid = _safe_model_id(model_id)
    meta = get_model_meta(mid)
    if meta is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": mid})
    return meta


@router.get("/models/{model_id}/graph")
async def onnx_model_graph(model_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_runtime()
    ensure_seed_models()
    mid = _safe_model_id(model_id)
    from backend.app.integrations.onnx.graph_summary import summarize_graph

    try:
        return summarize_graph(mid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": mid}) from None


@router.get("/models/{model_id}/file")
async def onnx_model_file(model_id: str, _user: dict[str, Any] = Depends(require_user)) -> FileResponse:
    _require_runtime()
    ensure_seed_models()
    mid = _safe_model_id(model_id)
    path = model_path(mid)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": mid})
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
        headers={"Cache-Control": "private, max-age=60"},
    )


def _run_train_job(job_id: str, body: TrainRequest) -> None:
    from backend.app.integrations.onnx.train import train_and_export

    _JOBS[job_id]["status"] = "running"
    try:
        bars = synthetic_candles(body.symbol, n=max(body.limit, 240))
        meta = train_and_export(
            model_id=body.model_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            bars=bars,
            source="synthetic_train",
            limit=body.limit,
            seed=body.seed,
        )
        _JOBS[job_id].update(
            {
                "status": "completed",
                "model_id": meta["id"],
                "test_mae": meta.get("test_mae"),
                "checksum": meta.get("checksum"),
                "version": meta.get("version"),
                "meta": meta,
            }
        )
    except Exception as exc:  # noqa: BLE001
        _JOBS[job_id].update({"status": "failed", "message": str(exc)})


@router.post("/train")
async def onnx_train(body: TrainRequest, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    _require_runtime()
    mid = _safe_model_id(body.model_id)
    body.model_id = mid
    job_id = uuid4().hex
    _JOBS[job_id] = {"job_id": job_id, "status": "queued", "model_id": mid}
    _run_train_job(job_id, body)
    return _JOBS[job_id]


@router.get("/train/{job_id}")
async def onnx_train_status(job_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": job_id})
    return job


@router.post("/infer")
async def onnx_infer(body: InferRequest, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    from backend.app.integrations.onnx.predictor import predict

    mid = _safe_model_id(body.model_id) if body.model_id else None
    if not body.allow_fallback:
        _require_runtime()
    bars = synthetic_candles(body.symbol, n=64)
    return predict(
        model_id=mid,
        symbol=body.symbol,
        bars=bars,
        source="synthetic",
        allow_fallback=body.allow_fallback,
    )
