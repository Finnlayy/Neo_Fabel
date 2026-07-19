"""ONNX Runtime inference for lstm_input [1,10,4]."""

from __future__ import annotations

import json
from typing import Any, Literal

import numpy as np

from backend.app.integrations.backtest.ema_grid import synthetic_candles
from backend.app.integrations.onnx.dataset import TARGET_FORMULAS, resolve_target, zscore_single
from backend.app.integrations.onnx.paths import meta_path, model_path


def _bars_to_window(bars: list[dict[str, Any]]) -> np.ndarray:
    if len(bars) < 10:
        raise ValueError("need at least 10 bars for inference window")
    window = bars[-10:]
    return np.array(
        [[float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])] for b in window],
        dtype=np.float32,
    )


def run_infer(
    *,
    model_id: str = "model4",
    symbol: str = "BTCUSD",
    bars: list[dict[str, Any]] | None = None,
    source: str = "synthetic",
) -> dict[str, Any]:
    import onnxruntime as ort

    mid = model_id.replace(".onnx", "")
    path = model_path(mid)
    if not path.exists():
        from backend.app.integrations.onnx.train import ensure_seed_models

        ensure_seed_models()
    if not path.exists():
        raise FileNotFoundError(f"model not found: {path}")

    if bars is None or len(bars) < 10:
        bars = synthetic_candles(symbol, n=64)
        source = "synthetic"

    window = _bars_to_window(bars)
    xn, mean_val, std_val = zscore_single(window)

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    out = session.run(None, {"lstm_input": xn})[0]
    prediction = float(np.asarray(out).reshape(-1)[0])

    meta: dict[str, Any] = {}
    mp = meta_path(mid)
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))

    target = resolve_target(mid)
    # Direction heuristics: for close target compare to last close; else use signed prediction
    last_close = float(bars[-1]["close"])
    if target == "close":
        delta = prediction - last_close
        direction: Literal["UP", "DOWN", "STABLE"] = (
            "UP" if delta > last_close * 0.0005 else "DOWN" if delta < -last_close * 0.0005 else "STABLE"
        )
        conf_base = min(99.5, 70 + abs(delta / max(last_close, 1e-6)) * 5000)
    else:
        direction = "UP" if prediction > 0.05 else "DOWN" if prediction < -0.05 else "STABLE"
        conf_base = min(99.5, 75 + abs(prediction) * 8)

    test_mae = float(meta.get("test_mae", 0.05))
    return {
        "prediction": round(prediction, 5),
        "direction": direction,
        "confidence": round(conf_base, 1),
        "testMae": test_mae,
        "onnxModel": f"{mid}.onnx",
        "syncStatus": "ORT LIVE" if source != "synthetic" else "ORT SYNTH",
        "isTraining": False,
        "meanVal": round(mean_val, 2),
        "stdVal": round(std_val, 3),
        "targetFormula": meta.get("target_formula") or TARGET_FORMULAS[target],
        "provider": "onnxruntime",
        "source": source,
    }
