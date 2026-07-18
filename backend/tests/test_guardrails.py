from decimal import Decimal

import pytest

from backend.app.trading.autonomy import AutonomyLevel, require_autonomy
from backend.app.trading.guardrails import GuardrailViolation, TradeRateLimiter, TradingGuardrails


def test_require_autonomy_blocks_below_level4():
    with pytest.raises(PermissionError):
        require_autonomy(AutonomyLevel.SUPERVISED, AutonomyLevel.AUTONOMOUS)


def test_require_autonomy_allows_level4():
    require_autonomy(AutonomyLevel.AUTONOMOUS, AutonomyLevel.AUTONOMOUS)


def test_guardrails_reject_unknown_pair():
    rails = TradingGuardrails(pair_allowlist=frozenset({"BTCUSD"}))
    with pytest.raises(GuardrailViolation) as exc:
        rails.check_order(pair="DOGEUSD", volume=Decimal("0.001"), open_positions=0)
    assert exc.value.code == "pair_not_allowed"


def test_guardrails_reject_oversized_order():
    rails = TradingGuardrails(max_order_size=Decimal("0.01"))
    with pytest.raises(GuardrailViolation) as exc:
        rails.check_order(pair="BTCUSD", volume=Decimal("0.5"), open_positions=0)
    assert exc.value.code == "max_order_size"


def test_guardrails_reject_too_many_open_positions():
    rails = TradingGuardrails(max_open_positions=2)
    with pytest.raises(GuardrailViolation) as exc:
        rails.check_order(pair="BTCUSD", volume=Decimal("0.001"), open_positions=2)
    assert exc.value.code == "max_open_positions"


def test_rate_limiter_blocks_after_max_trades():
    limiter = TradeRateLimiter(max_trades_per_hour=2)
    limiter.record_trade()
    limiter.record_trade()
    with pytest.raises(GuardrailViolation) as exc:
        limiter.assert_can_trade()
    assert exc.value.code == "max_trades_per_hour"


def test_guardrails_accept_valid_order():
    rails = TradingGuardrails(
        max_order_size=Decimal("0.01"),
        max_open_positions=3,
        pair_allowlist=frozenset({"BTCUSD", "ETHUSD"}),
    )
    assert rails.check_order(pair="btc/usd", volume=Decimal("0.005"), open_positions=1) == "BTCUSD"
