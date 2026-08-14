"""ONNX predictor façade — active model + ORT or mean fallback."""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.integrations.backtest.ema_grid import synthetic_candles
from backend.app.integrations.onnx.dataset import zscore_single
from backend.app.integrations.onnx.manifest import get_active
from backend.app.integrations.onnx.runtime import onnx_deps_available


def _bars_to_window(bars: list[dict[str, Any]]) -> np.ndarray:
    if len(bars) < 10:
        raise ValueError("need at least 10 bars for inference window")
    window = bars[-10:]
    return np.array(
        [[float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])] for b in window],
        dtype=np.float32,
    )


def _mean_fallback(window: np.ndarray, model_id: str, source: str) -> dict[str, Any]:
    xn, mean_val, std_val = zscore_single(window)
    flat = xn.reshape(-1)
    prediction = float(np.mean(flat)) if flat.size else 0.0
    return {
        "prediction": round(prediction, 5),
        "direction": "UP" if prediction > 0.05 else "DOWN" if prediction < -0.05 else "STABLE",
        "confidence": 55.0,
        "testMae": None,
        "onnxModel": f"{model_id}.onnx",
        "syncStatus": "MEAN FALLBACK",
        "isTraining": False,
        "meanVal": round(mean_val, 2),
        "stdVal": round(std_val, 3),
        "targetFormula": None,
        "provider": "mean_fallback",
        "source": source,
        "model_id": model_id,
    }


def predict(
    *,
    model_id: str | None = None,
    symbol: str = "BTCUSD",
    bars: list[dict[str, Any]] | None = None,
    source: str = "synthetic",
    allow_fallback: bool = True,
) -> dict[str, Any]:
    mid = (model_id or get_active()).replace(".onnx", "")
    if bars is None or len(bars) < 10:
        bars = synthetic_candles(symbol, n=64)
        source = "synthetic"
    window = _bars_to_window(bars)

    if not onnx_deps_available():
        if not allow_fallback:
            raise RuntimeError("onnx deps missing")
        return _mean_fallback(window, mid, source)

    try:
        from backend.app.integrations.onnx.infer import run_infer

        out = run_infer(model_id=mid, symbol=symbol, bars=bars, source=source)
        out["model_id"] = mid
        return out
    except Exception:
        if not allow_fallback:
            raise
        return _mean_fallback(window, mid, source)
