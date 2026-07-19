"""Phase 2 market stream / CCXT read-only tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.integrations.ccxt_market import CcxtMarketClient, compact_pair, to_ccxt_symbol
from backend.app.market.stream import MarketStreamHub, reset_market_stream_hub_for_tests
from backend.app.settings import Settings


def test_ccxt_symbol_helpers() -> None:
    assert to_ccxt_symbol("BTCUSD") == "BTC/USD"
    assert to_ccxt_symbol("eth/usd") == "ETH/USD"
    assert compact_pair("BTC/USD") == "BTCUSD"


def test_ccxt_client_rejects_credentials() -> None:
    client = CcxtMarketClient(exchange_id="kraken")
    client._exchange.apiKey = "secret-should-fail"  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="must not carry API credentials"):
        client._assert_read_only_surface()


@pytest.mark.asyncio
async def test_normalize_ticker_change_pct() -> None:
    client = CcxtMarketClient(exchange_id="kraken")
    try:
        row = client.normalize_ticker(
            "BTC/USD",
            {"last": 110.0, "open": 100.0, "percentage": None},
        )
        assert row["last"] == 110.0
        assert abs(float(row["change_pct"]) - 10.0) < 1e-6
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hub_fetch_falls_back_to_public() -> None:
    reset_market_stream_hub_for_tests()
    settings = Settings(
        MARKET_STREAM_ENABLED=True,
        MARKET_CCXT_ENABLED=True,
        MARKET_STREAM_SYMBOLS="BTC/USD",
    )
    hub = MarketStreamHub(settings)
    hub._ccxt = MagicMock()
    hub._ccxt.ticker_rows = AsyncMock(side_effect=RuntimeError("ccxt down"))

    with patch.object(
        hub,
        "_fetch_via_kraken_public",
        new=AsyncMock(
            return_value=[
                {"symbol": "BTC", "name": "Bitcoin", "price": 100.0, "change": 1.5, "pair": "BTCUSD"}
            ]
        ),
    ):
        snapshot = await hub._fetch_snapshot()

    assert snapshot["type"] == "tickers"
    assert snapshot["source"] == "kraken-public"
    assert snapshot["tickers"][0]["symbol"] == "BTC"
    assert snapshot["tickers"][0]["history"] == [100.0]


def test_hub_health_shape() -> None:
    settings = Settings(MARKET_STREAM_ENABLED=True, MARKET_CCXT_ENABLED=True)
    hub = MarketStreamHub(settings)
    health = hub.health()
    assert health["enabled"] is True
    assert health["ccxt_enabled"] is True
    assert health["exchange"] == "kraken"
    assert health["clients"] == 0
