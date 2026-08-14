"""Tests for FABLE_ENGINE_ONNX_BIAS integration."""

from __future__ import annotations

from decimal import Decimal

from backend.app.signals.engine.onnx_bias import apply_onnx_bias
from backend.app.signals.engine.strategies import SignalIntent


def _intent(side: str = "buy", volume: str = "1.0") -> SignalIntent:
    return SignalIntent(
        strategy_id="g1",
        kind="grid",
        pair="BTCUSD",
        side=side,  # type: ignore[arg-type]
        volume=Decimal(volume),
        reason="test",
    )


def test_off_mode_passthrough():
    intents = [_intent()]
    out = apply_onnx_bias(intents, mode="off", onnx=None)
    assert len(out) == 1
    assert out[0].volume == Decimal("1.0")
    assert "onnx" not in (out[0].meta or {})


def test_off_mode_attaches_meta_when_onnx_present():
    onnx = {"direction": "UP", "confidence": 70.0, "prediction": 0.1, "model_id": "model4"}
    out = apply_onnx_bias([_intent()], mode="off", onnx=onnx)
    assert out[0].meta and out[0].meta["onnx"]["direction"] == "UP"


def test_filter_mode_blocks_contradicting_buy_on_down():
    onnx = {"direction": "DOWN", "confidence": 75.0}
    out = apply_onnx_bias([_intent("buy")], mode="filter", onnx=onnx)
    assert out == []


def test_filter_mode_allows_aligned_buy_on_up():
    onnx = {"direction": "UP", "confidence": 75.0}
    out = apply_onnx_bias([_intent("buy")], mode="filter", onnx=onnx)
    assert len(out) == 1


def test_scale_mode_increases_volume_on_alignment():
    onnx = {"direction": "UP", "confidence": 90.0}
    out = apply_onnx_bias([_intent("buy", "1.0")], mode="scale", onnx=onnx)
    assert len(out) == 1
    assert out[0].volume > Decimal("1.0")
    assert out[0].meta and out[0].meta.get("onnx_scale_factor", 0) > 1.0


def test_scale_mode_reduces_volume_on_contradiction():
    onnx = {"direction": "DOWN", "confidence": 90.0}
    out = apply_onnx_bias([_intent("buy", "1.0")], mode="scale", onnx=onnx)
    assert len(out) == 1
    assert out[0].volume < Decimal("1.0")
