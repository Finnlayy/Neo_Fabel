"""Tests for session risk policy helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.trading.session_policy import (
    assert_confidence_ok,
    assert_daily_loss_ok,
    assert_market_hours_allowed,
    parse_cap_amount,
    validate_session_risk_policy,
)


def test_parse_cap_units():
    assert parse_cap_amount({"value": 10, "unit": "eur"}).unit == "eur"
    assert parse_cap_amount("5%").unit == "pct"
    assert parse_cap_amount("$12").unit == "usd"
    assert parse_cap_amount(8).resolve_eur(capital_eur=100) == 8
    assert parse_cap_amount({"value": 20, "unit": "pct"}).resolve_eur(capital_eur=50) == 10


def test_validate_policy_and_bounds():
    policy = validate_session_risk_policy(
        max_session_size={"value": 10, "unit": "eur"},
        max_concurrent_trades=2,
        daily_loss_limit={"value": 5, "unit": "pct"},
        min_confidence_pct=60,
        allow_pre_post_market=False,
        human_verification=True,
        starting_capital_eur=100,
    )
    assert policy.max_session_size_eur() == 10
    assert policy.daily_loss_limit_eur() == 5
    assert policy.human_verification is True

    with pytest.raises(ValueError, match="1..10"):
        validate_session_risk_policy(
            max_session_size=10,
            max_concurrent_trades=11,
            daily_loss_limit=1,
            starting_capital_eur=100,
        )


def test_confidence_and_daily_loss_gates():
    assert_confidence_ok(70, min_confidence_pct=60)
    with pytest.raises(ValueError):
        assert_confidence_ok(50, min_confidence_pct=60)
    assert_daily_loss_ok(realized_loss_eur=2, daily_loss_limit_eur=5)
    with pytest.raises(ValueError):
        assert_daily_loss_ok(realized_loss_eur=5, daily_loss_limit_eur=5)


def test_pre_post_market_blocks_equity_outside_hours():
    # Monday 10:00 UTC — before US cash open
    stamp = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="pre/post"):
        assert_market_hours_allowed("METAUSD", allow_pre_post_market=False, now=stamp)
    # Crypto always allowed
    assert_market_hours_allowed("XRPUSD", allow_pre_post_market=False, now=stamp)
    # Allowed when flag on
    assert_market_hours_allowed("METAUSD", allow_pre_post_market=True, now=stamp)
