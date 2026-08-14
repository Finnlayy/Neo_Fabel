"""ONNX artifact paths under backend/data/onnx."""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ONNX_DATA_DIR = BACKEND_ROOT / "data" / "onnx"


def ensure_onnx_data_dir() -> Path:
    ONNX_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return ONNX_DATA_DIR


def model_path(model_id: str) -> Path:
    safe = "".join(c for c in model_id if c.isalnum() or c in ("_", "-", ".")).strip(".")
    if not safe:
        raise ValueError("invalid model_id")
    if not safe.endswith(".onnx"):
        safe = f"{safe}.onnx"
    return ensure_onnx_data_dir() / safe


def meta_path(model_id: str) -> Path:
    p = model_path(model_id)
    return p.with_suffix(".meta.json")


def manifest_path() -> Path:
    return ensure_onnx_data_dir() / "manifest.json"
