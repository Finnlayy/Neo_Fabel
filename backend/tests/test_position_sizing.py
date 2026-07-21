"""Unit tests for live session position sizing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.trading.position_sizing import (
    compute_notional_eur,
    kelly_fraction,
    parse_sizing_mode,
    validate_sizing_policy,
    volume_from_notional,
)


def test_parse_sizing_aliases():
    assert parse_sizing_mode("Half Kelly") == "half_kelly"
    assert parse_sizing_mode("full") == "full_kelly"
    assert parse_sizing_mode("chronos") == "ai_chronos"
    assert parse_sizing_mode("manual") == "manual"


def test_manual_requires_notional():
    with pytest.raises(ValueError, match="manual_notional"):
        validate_sizing_policy(mode="manual")


def test_half_kelly_smaller_than_full():
    half = validate_sizing_policy(mode="half_kelly")
    full = validate_sizing_policy(mode="full_kelly")
    h = compute_notional_eur(half, capital_eur=100, confidence=0.7, stop_pct=0.03, take_pct=0.06)
    f = compute_notional_eur(full, capital_eur=100, confidence=0.7, stop_pct=0.03, take_pct=0.06)
    assert h["notional_eur"] <= f["notional_eur"]
    assert h["notional_eur"] > 0


def test_manual_notional_capped_by_margin():
    policy = validate_sizing_policy(mode="manual", manual_notional_eur=20)
    out = compute_notional_eur(policy, capital_eur=100, max_margin_eur=10)
    assert out["notional_eur"] == 10


def test_ai_chronos_uses_confidence():
    policy = validate_sizing_policy(mode="ai_chronos")
    out = compute_notional_eur(policy, capital_eur=100, ai_confidence=0.8)
    assert out["mode"] == "ai_chronos"
    assert 0 < out["notional_eur"] <= 25  # max_fraction default 0.25


def test_kelly_math_basic():
    # p=0.6, b=2 → f* = (0.6*2 - 0.4)/2 = 0.4; half = 0.2
    assert kelly_fraction(win_prob=0.6, payoff_ratio=2.0, scale=0.5) == pytest.approx(0.2)


def test_volume_from_notional():
    vol = volume_from_notional(notional_eur=10, price=Decimal("2"))
    assert vol == Decimal("5.00000000")
