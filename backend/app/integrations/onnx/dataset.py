"""Sliding OHLC windows → X [N,10,4], y [N] with per-window Z-score option."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

TargetName = Literal["close", "spread_skew", "range_momentum"]

TARGET_FORMULAS: dict[str, str] = {
    "close": "y = next_bar.close",
    "spread_skew": "y = (high - open) - (open - low)",
    "range_momentum": "y = (high - high_prev) + (low - low_prev)",
}

MODEL_TARGETS: dict[str, TargetName] = {
    "model": "close",
    "model.onnx": "close",
    "model2": "spread_skew",
    "model2.onnx": "spread_skew",
    "model4": "range_momentum",
    "model4.onnx": "range_momentum",
}

HISTORY = 10
FEATURE_SET = "ohlc_v1"


def resolve_target(model_id: str) -> TargetName:
    key = model_id if model_id in MODEL_TARGETS else model_id.replace(".onnx", "")
    return MODEL_TARGETS.get(key, MODEL_TARGETS.get(f"{key}.onnx", "range_momentum"))


def _bar_ohlc(bar: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(bar["open"]),
        float(bar["high"]),
        float(bar["low"]),
        float(bar["close"]),
    )


def _target_value(bars: list[dict[str, Any]], i: int, target: TargetName) -> float:
    """Target at index i uses bar i as 'current' and i+1 as next where needed."""
    o, h, low, c = _bar_ohlc(bars[i])
    if target == "close":
        return float(bars[i + 1]["close"])
    if target == "spread_skew":
        return (h - o) - (o - low)
    # range_momentum
    if i == 0:
        return 0.0
    _po, ph, pl, _pc = _bar_ohlc(bars[i - 1])
    return (h - ph) + (low - pl)


def collect_windows(
    bars: list[dict[str, Any]],
    *,
    target: TargetName,
    history_size: int = HISTORY,
) -> tuple[np.ndarray, np.ndarray]:
    """
    bars: oldest-first OHLC dicts.
    Returns X float32 [N, history, 4], y float32 [N].
    For close target, last usable index is len-2 (needs next bar).
    """
    if len(bars) < history_size + 2:
        raise ValueError(f"need at least {history_size + 2} bars, got {len(bars)}")

    xs: list[np.ndarray] = []
    ys: list[float] = []
    last_i = len(bars) - 2 if target == "close" else len(bars) - 1
    for end in range(history_size - 1, last_i + 1):
        start = end - history_size + 1
        window = bars[start : end + 1]
        arr = np.array([_bar_ohlc(b) for b in window], dtype=np.float64)
        xs.append(arr)
        ys.append(_target_value(bars, end, target))

    X = np.stack(xs, axis=0).astype(np.float32)
    y = np.asarray(ys, dtype=np.float32)
    return X, y


def zscore_windows(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-window Z-score over the history×features plane. Returns Xn, means[N], stds[N]."""
    flat = X.reshape(X.shape[0], -1)
    means = flat.mean(axis=1)
    stds = flat.std(axis=1)
    stds = np.where(stds < 1e-6, 1.0, stds)
    xn = ((flat - means[:, None]) / stds[:, None]).reshape(X.shape).astype(np.float32)
    return xn, means.astype(np.float32), stds.astype(np.float32)


def zscore_single(window: np.ndarray) -> tuple[np.ndarray, float, float]:
    """window [10,4] → normalized [1,10,4], mean, std."""
    x = window.astype(np.float32)[None, ...]
    xn, means, stds = zscore_windows(x)
    return xn, float(means[0]), float(stds[0])
