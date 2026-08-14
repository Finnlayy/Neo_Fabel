"""Train linear proxy on OHLC windows and export ONNX + meta."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np

from backend.app.integrations.backtest.ema_grid import synthetic_candles
from backend.app.integrations.onnx.dataset import (
    FEATURE_SET,
    TARGET_FORMULAS,
    collect_windows,
    resolve_target,
    zscore_windows,
)
from backend.app.integrations.onnx.export_onnx import export_linear_onnx
from backend.app.integrations.onnx.manifest import file_checksum, register_model
from backend.app.integrations.onnx.paths import meta_path, model_path


def _normalize_model_id(model_id: str) -> str:
    mid = model_id.strip().replace(".onnx", "")
    if mid not in {"model", "model2", "model4"}:
        mid = "model4"
    return mid


def train_and_export(
    *,
    model_id: str = "model4",
    symbol: str = "BTCUSD",
    timeframe: str = "1h",
    bars: list[dict[str, Any]] | None = None,
    source: str = "synthetic",
    limit: int = 400,
    seed: int | None = None,
) -> dict[str, Any]:
    mid = _normalize_model_id(model_id)
    target = resolve_target(mid)
    if seed is not None:
        np.random.seed(int(seed))
    if bars is None or len(bars) < 30:
        bars = synthetic_candles(symbol, n=max(limit, 240))
        source = "synthetic"

    bars = bars[-limit:] if len(bars) > limit else bars
    X, y = collect_windows(bars, target=target)
    Xn, _means, _stds = zscore_windows(X)
    flat = Xn.reshape(Xn.shape[0], -1)

    # Ridge-ish least squares for stability
    lam = 1e-3
    xtx = flat.T @ flat + lam * np.eye(flat.shape[1], dtype=np.float32)
    xty = flat.T @ y
    coef = np.linalg.solve(xtx, xty).astype(np.float32)  # (40,)
    pred = flat @ coef
    mae = float(np.mean(np.abs(pred - y)))
    bias = np.array([float(np.mean(y - pred))], dtype=np.float32)

    out = model_path(mid)
    export_linear_onnx(coef.reshape(40, 1), bias, out)
    now = datetime.now(UTC)
    version = now.strftime("%Y%m%d.%H%M%S")
    checksum = file_checksum(out)

    meta = {
        "id": mid,
        "filename": out.name,
        "target": target,
        "target_formula": TARGET_FORMULAS[target],
        "test_mae": round(mae, 6),
        "trained_at": now.isoformat(),
        "created": now.isoformat(),
        "version": version,
        "checksum": checksum,
        "feature_set": FEATURE_SET,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "source": source,
        "samples": int(X.shape[0]),
        "input_name": "lstm_input",
        "input_shape": [1, 10, 4],
        "architecture": "flatten_gemm_proxy",
    }
    if seed is not None:
        meta["seed"] = int(seed)
    meta_path(mid).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    register_model(meta)
    return meta


def ensure_seed_models() -> list[dict[str, Any]]:
    """Create model / model2 / model4 seed ONNX files if missing."""
    metas: list[dict[str, Any]] = []
    for mid in ("model", "model2", "model4"):
        if not model_path(mid).exists():
            metas.append(
                train_and_export(model_id=mid, symbol="BTCUSD", source="seed_synthetic", limit=320, seed=42)
            )
        else:
            mp = meta_path(mid)
            if mp.exists():
                metas.append(json.loads(mp.read_text(encoding="utf-8")))
    return metas
