"""Summarize ONNX graph ops and weight fingerprints (train visibility)."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from backend.app.integrations.onnx.paths import model_path


def summarize_graph(model_id: str) -> dict[str, Any]:
    import onnx
    from onnx import numpy_helper

    mid = model_id.replace(".onnx", "")
    path = model_path(mid)
    if not path.exists():
        raise FileNotFoundError(mid)

    model = onnx.load(str(path))
    graph = model.graph
    ops = [node.op_type for node in graph.node]
    initializers: list[dict[str, Any]] = []
    weight_parts: list[bytes] = []

    for init in graph.initializer:
        arr = numpy_helper.to_array(init).astype(np.float32, copy=False)
        flat = arr.reshape(-1)
        digest = hashlib.sha256(flat.tobytes()).hexdigest()[:16]
        entry = {
            "name": init.name,
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "mean": float(np.mean(flat)) if flat.size else 0.0,
            "std": float(np.std(flat)) if flat.size else 0.0,
            "l2": float(np.linalg.norm(flat)) if flat.size else 0.0,
            "sha256_16": digest,
        }
        initializers.append(entry)
        weight_parts.append(flat.tobytes())

    combined = hashlib.sha256(b"".join(weight_parts)).hexdigest() if weight_parts else ""
    return {
        "id": mid,
        "ops": ops,
        "op_counts": {op: ops.count(op) for op in sorted(set(ops))},
        "initializers": initializers,
        "weight_fingerprint": combined[:32] if combined else "",
        "node_count": len(graph.node),
        "architecture_hint": "flatten_gemm_proxy" if ops == ["Flatten", "Gemm"] else "custom",
    }
