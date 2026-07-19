"""Dependency probes and Netron static discovery."""

from __future__ import annotations

from pathlib import Path


def onnx_deps_available() -> bool:
    try:
        import numpy  # noqa: F401
        import onnx  # noqa: F401
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def netron_static_dir() -> Path | None:
    try:
        import netron
    except ImportError:
        return None
    root = Path(netron.__file__).resolve().parent
    for candidate in (root, root / "dist", root / "source"):
        if (candidate / "index.html").exists():
            return candidate
    # Netron packages often ship index.html next to __init__.py
    matches = list(root.rglob("index.html"))
    for m in matches:
        if "test" not in str(m).lower():
            return m.parent
    return None


def ensure_seed_models() -> list[dict]:
    if not onnx_deps_available():
        return []
    from backend.app.integrations.onnx.train import ensure_seed_models as _seed

    return _seed()
