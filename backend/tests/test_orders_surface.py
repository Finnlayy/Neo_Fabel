"""Tests for expanded order schemas / Kraken CLI validation."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.integrations.kraken_cli import SPOT_ORDER_TYPES, KrakenCli, KrakenCliError
from backend.app.schemas import CancelAllOrdersRequest, PlaceOrderRequest


def test_spot_order_types_cover_kraken_surface():
    assert "trailing-stop" in SPOT_ORDER_TYPES
    assert "stop-loss-limit" in SPOT_ORDER_TYPES


def test_place_order_request_accepts_trailing_offset_string():
    req = PlaceOrderRequest(
        mode="live",
        pair="BTCUSD",
        side="sell",
        volume=Decimal("0.001"),
        order_type="trailing-stop",
        price="+500",
        idempotency_key=uuid4(),
    )
    assert req.price == "+500"


def test_cancel_all_requires_confirm_default_false():
    body = CancelAllOrdersRequest()
    assert body.confirm is False


@pytest.mark.asyncio
async def test_place_order_disabled_without_trade_commands():
    cli = KrakenCli(allow_trade_commands=False)
    with pytest.raises(KrakenCliError) as exc:
        await cli.place_order("buy", "BTCUSD", Decimal("0.001"), "market", None, yes=True)
    assert exc.value.category == "validation"


@pytest.mark.asyncio
async def test_cancel_order_disabled_without_trade_commands():
    cli = KrakenCli(allow_trade_commands=False)
    with pytest.raises(KrakenCliError):
        await cli.cancel_order("TXID")
