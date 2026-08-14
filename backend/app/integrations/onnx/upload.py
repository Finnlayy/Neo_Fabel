"""Accept user-uploaded ONNX files into the paper research registry."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.integrations.onnx.dataset import FEATURE_SET
from backend.app.integrations.onnx.manifest import file_checksum, register_model, set_active
from backend.app.integrations.onnx.paths import ensure_onnx_data_dir, meta_path, model_path

_MODEL_ID_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB


def _normalize_upload_id(model_id: str | None, filename: str | None) -> str:
    raw = (model_id or "").strip() or (filename or "").strip()
    mid = Path(raw).name.replace(".onnx", "").replace(".ONNX", "")
    mid = "".join(c for c in mid if c.isalnum() or c in ("_", "-", ".")).strip(".")
    if not mid or not _MODEL_ID_RE.match(mid):
        raise ValueError("invalid model_id")
    return mid


def save_uploaded_onnx(
    *,
    data: bytes,
    filename: str | None = None,
    model_id: str | None = None,
    make_active: bool = False,
    source: str = "upload",
) -> dict[str, Any]:
    if not data:
        raise ValueError("empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"file too large (max {MAX_UPLOAD_BYTES} bytes)")

    mid = _normalize_upload_id(model_id, filename)
    ensure_onnx_data_dir()
    out = model_path(mid)

    # Write to temp then validate before replace
    tmp = out.with_suffix(".onnx.uploading")
    tmp.write_bytes(data)
    try:
        import onnx
        from onnx.checker import check_model

        model = onnx.load(str(tmp))
        check_model(model)
        input_name = model.graph.input[0].name if model.graph.input else "lstm_input"
        input_shape: list[Any] = []
        if model.graph.input:
            for d in model.graph.input[0].type.tensor_type.shape.dim:
                input_shape.append(d.dim_value if d.dim_value else None)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise ValueError(f"invalid onnx: {exc}") from exc

    tmp.replace(out)
    now = datetime.now(UTC)
    version = now.strftime("%Y%m%d.%H%M%S")
    checksum = file_checksum(out)
    meta = {
        "id": mid,
        "filename": out.name,
        "target": "uploaded",
        "target_formula": "user-uploaded ONNX",
        "test_mae": None,
        "trained_at": now.isoformat(),
        "created": now.isoformat(),
        "version": version,
        "checksum": checksum,
        "feature_set": FEATURE_SET,
        "symbol": None,
        "timeframe": None,
        "source": source,
        "samples": None,
        "input_name": input_name,
        "input_shape": input_shape or [1, 10, 4],
        "architecture": "uploaded",
        "original_filename": filename,
    }
    meta_path(mid).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    register_model(meta)
    if make_active:
        set_active(mid)
    return meta
