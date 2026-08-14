"""Capital policy: no external top-ups, no debt, no negative cash."""

from decimal import Decimal

import pytest

from backend.app.trading.capital_policy import (
    assert_args_forbid_external_capital,
    assert_buy_affordable,
    assert_live_order_capital,
    assert_max_notional,
    assert_no_debt_leverage,
    assert_sell_covered,
    cash_balance_quote,
    cash_balance_usd,
)
from backend.app.trading.guardrails import GuardrailViolation


def test_blocks_deposit_withdraw_transfer_argv():
    with pytest.raises(GuardrailViolation) as exc:
        assert_args_forbid_external_capital(["deposit", "methods"])
    assert exc.value.code == "external_capital_forbidden"
    with pytest.raises(GuardrailViolation):
        assert_args_forbid_external_capital(["withdraw", "USD", "1"])
    with pytest.raises(GuardrailViolation):
        assert_args_forbid_external_capital(["transfer", "spot", "futures"])


def test_allows_normal_trade_argv():
    assert_args_forbid_external_capital(["order", "buy", "ADAUSD", "1", "--type", "market"])


def test_cash_balance_reads_zusd():
    assert cash_balance_usd({"ZUSD": "4.25", "ADA": "10"}) == Decimal("4.25")


def test_cash_balance_counts_zeur():
    assert cash_balance_quote({"ZEUR": "4.00", "ADA": "1"}) == Decimal("4.00")
    assert cash_balance_quote({"ZEUR": "2", "ZUSD": "1"}) == Decimal("3")


def test_max_notional_blocks_oversized_buy():
    with pytest.raises(GuardrailViolation) as exc:
        assert_max_notional(
            volume=Decimal("10"),
            price=Decimal("0.5"),
            max_notional=Decimal("2"),
        )
    assert exc.value.code == "max_notional"


def test_buy_rejected_when_insufficient_cash():
    with pytest.raises(GuardrailViolation) as exc:
        assert_buy_affordable(cash=Decimal("4"), volume=Decimal("10"), price=Decimal("1"))
    assert exc.value.code == "insufficient_cash"


def test_sell_rejected_when_short():
    with pytest.raises(GuardrailViolation) as exc:
        assert_sell_covered(held=Decimal("1"), volume=Decimal("2"))
    assert exc.value.code == "insufficient_inventory"


def test_leverage_and_futures_open_blocked():
    with pytest.raises(GuardrailViolation) as exc:
        assert_no_debt_leverage(leverage=5, market_type="spot")
    assert exc.value.code == "debt_forbidden"
    with pytest.raises(GuardrailViolation):
        assert_no_debt_leverage(leverage=1, market_type="futures", reduce_only=False)
    assert_no_debt_leverage(leverage=1, market_type="futures", reduce_only=True)


def test_live_order_capital_buy_ok():
    assert_live_order_capital(
        side="buy",
        pair="ADAUSD",
        volume=Decimal("2"),
        price=Decimal("0.5"),
        balance_payload={"ZUSD": "4.00"},
        leverage=1,
    )
