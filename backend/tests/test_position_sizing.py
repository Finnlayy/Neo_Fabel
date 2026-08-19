"""Unit tests for live session position sizing."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.settings import Settings
from backend.app.trading.position_sizing import (
    compute_notional_eur,
    kelly_fraction,
    parse_sizing_mode,
    validate_sizing_policy,
    volume_from_notional,
)
from backend.app.trading.session import Level4Session
from backend.app.trading.session_policy import validate_session_risk_policy


def test_parse_sizing_aliases():
    assert parse_sizing_mode("Dynamic Kelly") == "dynamic_kelly"
    assert parse_sizing_mode("fixed usd") == "fixed_usd"
    assert parse_sizing_mode("Half Kelly") == "half_kelly"
    assert parse_sizing_mode("full") == "full_kelly"
    assert parse_sizing_mode("chronos") == "ai_chronos"
    assert parse_sizing_mode("manual") == "manual"


def test_manual_requires_notional():
    with pytest.raises(ValueError, match="manual_notional"):
        validate_sizing_policy(mode="manual")


def test_dynamic_kelly_scales_risk_from_1_5_to_5_percent():
    policy = validate_sizing_policy(mode="dynamic_kelly")
    low = compute_notional_eur(policy, capital_eur=1000, confidence=0.5)
    mid = compute_notional_eur(policy, capital_eur=1000, confidence=0.75)
    high = compute_notional_eur(policy, capital_eur=1000, confidence=1.0)
    assert low["notional_eur"] == pytest.approx(15)
    assert mid["notional_eur"] == pytest.approx(32.5)
    assert high["notional_eur"] == pytest.approx(50)


def test_fixed_usd_requires_and_uses_fixed_notional():
    with pytest.raises(ValueError, match="fixed_notional_usd"):
        validate_sizing_policy(mode="fixed_usd")
    policy = validate_sizing_policy(mode="fixed_usd", fixed_notional_usd=25)
    out = compute_notional_eur(policy, capital_eur=1000, max_margin_eur=100)
    assert out["notional_eur"] == 25


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
    vol = volume_from_notional(notional_eur=10, price=Decimal(2))
    assert vol == Decimal("5.00000000")


@pytest.mark.asyncio
async def test_live_entry_uses_dynamic_kelly_instead_of_requested_volume(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_pair_allowlist="ADAUSD",
        kraken_max_order_size=Decimal(100),
        kraken_max_notional=Decimal(1000),
        kraken_min_trade_interval_seconds=0,
    )
    cli = MagicMock()
    cli.ticker = AsyncMock(return_value={"last": "0.50"})
    cli.open_orders = AsyncMock(return_value={"open": {}})
    cli.balance = AsyncMock(return_value={"ZUSD": "1000"})
    cli.validate_order = AsyncMock(return_value={"ok": True})
    cli.place_order = AsyncMock(return_value={"txid": ["LIVE-1"]})
    session = Level4Session(settings, cli=cli)
    session._deadman_armed = True
    session.set_sizing_policy(
        validate_sizing_policy(mode="dynamic_kelly"),
        capital_eur=1000,
        max_margin_eur=1000,
    )
    session.set_risk_policy(
        validate_session_risk_policy(
            max_session_size={"value": 1000, "unit": "usd"},
            max_concurrent_trades=2,
            daily_loss_limit={"value": 50, "unit": "usd"},
            max_drawdown_usd={"value": 100, "unit": "usd"},
            min_confidence_pct=50,
            starting_capital_eur=1000,
        )
    )
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.assert_safe_to_trade_pair",
        lambda _pair: None,
    )

    result = await session.execute_order(
        "buy",
        "ADAUSD",
        Decimal(999),
        "market",
        None,
        confidence_pct=75,
    )

    placed_volume = cli.place_order.await_args.args[2]
    assert placed_volume == Decimal("65.00000000")
    assert result["position_sizing"]["fraction"] == pytest.approx(0.0325)
