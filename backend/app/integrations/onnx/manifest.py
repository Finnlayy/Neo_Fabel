"""Read/write ONNX model manifest / per-model meta / active pin."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.app.integrations.onnx.paths import ensure_onnx_data_dir, manifest_path, meta_path, model_path

DEFAULT_ACTIVE_MODEL_ID = "model4"


def file_checksum(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_registry() -> dict[str, Any]:
    ensure_onnx_data_dir()
    path = manifest_path()
    if not path.exists():
        return {"active_model_id": DEFAULT_ACTIVE_MODEL_ID, "models": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"active_model_id": DEFAULT_ACTIVE_MODEL_ID, "models": []}
    if not isinstance(data, dict):
        return {"active_model_id": DEFAULT_ACTIVE_MODEL_ID, "models": []}
    data.setdefault("active_model_id", DEFAULT_ACTIVE_MODEL_ID)
    data.setdefault("models", [])
    return data


def _write_registry(data: dict[str, Any]) -> None:
    ensure_onnx_data_dir()
    path = manifest_path()
    payload = {
        "active_model_id": data.get("active_model_id") or DEFAULT_ACTIVE_MODEL_ID,
        "models": list(data.get("models") or []),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_active() -> str:
    mid = str(_read_registry().get("active_model_id") or DEFAULT_ACTIVE_MODEL_ID).replace(".onnx", "")
    return mid or DEFAULT_ACTIVE_MODEL_ID


def set_active(model_id: str) -> str:
    mid = model_id.replace(".onnx", "").strip()
    if not mid:
        raise ValueError("empty model_id")
    path = model_path(mid)
    if not path.exists():
        raise FileNotFoundError(mid)
    data = _read_registry()
    data["active_model_id"] = mid
    _write_registry(data)
    return mid


def register_model(meta: dict[str, Any]) -> dict[str, Any]:
    """Upsert model meta into manifest.json; preserve active_model_id."""
    data = _read_registry()
    models = [m for m in data.get("models", []) if m.get("id") != meta.get("id")]
    models.append(dict(meta))
    models.sort(key=lambda m: str(m.get("id", "")))
    data["models"] = models
    if not data.get("active_model_id"):
        data["active_model_id"] = DEFAULT_ACTIVE_MODEL_ID
    _write_registry(data)
    return meta


def _with_file_revision(meta: dict[str, Any]) -> dict[str, Any]:
    """Attach mtime so Netron embeds can cache-bust when weights rewrite the same graph."""
    mid = str(meta.get("id") or "").replace(".onnx", "")
    path = model_path(mid) if mid else None
    out = dict(meta)
    out.setdefault("architecture", "flatten_gemm_proxy")
    out.setdefault("feature_set", "ohlc_v1")
    if path is not None and path.exists():
        out["file_mtime"] = int(path.stat().st_mtime)
        out["file_size"] = int(path.stat().st_size)
        if not out.get("checksum"):
            out["checksum"] = file_checksum(path)
    return out


def list_models() -> list[dict[str, Any]]:
    ensure_onnx_data_dir()
    data = _read_registry()
    models = list(data.get("models") or [])
    if models:
        return [_with_file_revision(m) for m in models]
    # Fallback: scan directory
    out: list[dict[str, Any]] = []
    for onnx_file in sorted(ensure_onnx_data_dir().glob("*.onnx")):
        mid = onnx_file.stem
        mp = meta_path(mid)
        if mp.exists():
            out.append(_with_file_revision(json.loads(mp.read_text(encoding="utf-8"))))
        else:
            out.append(
                _with_file_revision(
                    {"id": mid, "filename": onnx_file.name, "input_name": "lstm_input", "input_shape": [1, 10, 4]}
                )
            )
    return out


def get_model_meta(model_id: str) -> dict[str, Any] | None:
    mid = model_id.replace(".onnx", "")
    mp = meta_path(mid)
    if mp.exists():
        return _with_file_revision(json.loads(mp.read_text(encoding="utf-8")))
    if model_path(mid).exists():
        return _with_file_revision(
            {"id": mid, "filename": model_path(mid).name, "input_name": "lstm_input", "input_shape": [1, 10, 4]}
        )
    return None
