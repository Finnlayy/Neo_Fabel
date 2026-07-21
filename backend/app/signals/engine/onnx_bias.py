"""ONNX bias integration for FableEngine — off | filter | scale."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from backend.app.signals.engine.strategies import SignalIntent

OnnxBiasMode = Literal["off", "filter", "scale"]


def _side_bias(side: str) -> Literal["bullish", "bearish", "neutral"]:
    s = side.lower()
    if s == "buy":
        return "bullish"
    if s == "sell":
        return "bearish"
    return "neutral"


def _onnx_bias(onnx: dict[str, Any]) -> Literal["bullish", "bearish", "neutral"]:
    direction = str(onnx.get("direction") or "STABLE").upper()
    if direction == "UP":
        return "bullish"
    if direction == "DOWN":
        return "bearish"
    return "neutral"


def apply_onnx_bias(
    intents: list[SignalIntent],
    *,
    mode: OnnxBiasMode,
    onnx: dict[str, Any] | None,
) -> list[SignalIntent]:
    """Apply FABLE_ENGINE_ONNX_BIAS to engine intents.

    - off: pass through (onnx recorded in meta only when provided)
    - filter: drop intents that contradict ONNX direction (when confidence >= 55)
    - scale: multiply volume by alignment factor (0.5–1.5)
    """
    if not intents:
        return intents

    if mode == "off" or not onnx:
        if onnx:
            return [_attach_onnx_meta(i, onnx) for i in intents]
        return intents

    ob = _onnx_bias(onnx)
    conf = float(onnx.get("confidence") or 0.0)

    if mode == "filter":
        if ob == "neutral" or conf < 55.0:
            return [_attach_onnx_meta(i, onnx) for i in intents]
        out: list[SignalIntent] = []
        for intent in intents:
            ib = _side_bias(intent.side)
            if ib != "neutral" and ib != ob:
                continue
            out.append(_attach_onnx_meta(intent, onnx))
        return out

    if mode == "scale":
        scaled: list[SignalIntent] = []
        for intent in intents:
            ib = _side_bias(intent.side)
            factor = _scale_factor(ib, ob, conf)
            new_vol = (intent.volume * Decimal(str(factor))).quantize(Decimal("0.00000001"))
            if new_vol <= 0:
                continue
            meta = dict(intent.meta or {})
            meta["onnx_scale_factor"] = factor
            meta["onnx"] = _onnx_summary(onnx)
            scaled.append(
                SignalIntent(
                    strategy_id=intent.strategy_id,
                    kind=intent.kind,
                    pair=intent.pair,
                    side=intent.side,
                    volume=new_vol,
                    reason=intent.reason,
                    zone=intent.zone,
                    price=intent.price,
                    meta=meta,
                )
            )
        return scaled

    return intents


def _scale_factor(
    intent_bias: Literal["bullish", "bearish", "neutral"],
    onnx_bias: Literal["bullish", "bearish", "neutral"],
    confidence: float,
) -> float:
    if intent_bias == "neutral" or onnx_bias == "neutral":
        return 1.0
    align = intent_bias == onnx_bias
    strength = min(1.0, max(0.0, (confidence - 50.0) / 50.0))
    if align:
        return 1.0 + 0.5 * strength
    return max(0.5, 1.0 - 0.5 * strength)


def _onnx_summary(onnx: dict[str, Any]) -> dict[str, Any]:
    return {
        "direction": onnx.get("direction"),
        "confidence": onnx.get("confidence"),
        "prediction": onnx.get("prediction"),
        "model_id": onnx.get("model_id") or onnx.get("onnxModel"),
    }


def _attach_onnx_meta(intent: SignalIntent, onnx: dict[str, Any]) -> SignalIntent:
    meta = dict(intent.meta or {})
    meta["onnx"] = _onnx_summary(onnx)
    return SignalIntent(
        strategy_id=intent.strategy_id,
        kind=intent.kind,
        pair=intent.pair,
        side=intent.side,
        volume=intent.volume,
        reason=intent.reason,
        zone=intent.zone,
        price=intent.price,
        meta=meta,
    )
