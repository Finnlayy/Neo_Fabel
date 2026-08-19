"""Spot/futures instrument normalization."""

from decimal import Decimal

import pytest

from backend.app.market.instruments import (
    futures_symbol_for_spot,
    normalize_symbol,
    resolve_instrument,
)


def test_normalize_spot_aliases() -> None:
    assert normalize_symbol("BTC/USD") == "BTCUSD"
    assert normalize_symbol("XBTUSD") == "BTCUSD"


def test_futures_symbol_mapping() -> None:
    assert futures_symbol_for_spot("BTCUSD") == "PF_XBTUSD"
    assert futures_symbol_for_spot("ETHUSD") == "PF_ETHUSD"


def test_resolve_futures_instrument() -> None:
    inst = resolve_instrument("futures", "BTCUSD", leverage=3)
    assert inst.market_type == "futures"
    assert inst.symbol == "PF_XBTUSD"
    assert inst.canonical_id == "futures:PF_XBTUSD"


@pytest.mark.asyncio
async def test_futures_paper_order_margin_gate() -> None:
    from unittest.mock import AsyncMock

    from backend.app.integrations.local_paper import LocalPaperLedger

    ledger = LocalPaperLedger(starting_margin_usd=Decimal(100), kelly_sizing_enabled=False)
    ledger.set_price_resolver(AsyncMock(return_value=Decimal(50000)))
    with pytest.raises(ValueError, match="insufficient futures margin"):
        await ledger.paper_order(
            "buy",
            "BTCUSD",
            Decimal(1),
            "market",
            None,
            market_type="futures",
            leverage=1,
        )
