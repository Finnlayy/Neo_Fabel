"""Kraken public REST helpers used for Windows-safe live tickers."""

import asyncio

from backend.app.integrations.kraken_public import (
    PAIR_ALIASES,
    KrakenPublicClient,
    normalize_orderbook_levels,
)


def test_btc_alias_maps_to_xbt():
    client = KrakenPublicClient()
    assert client._pair("BTCUSD") == "XBTUSD"
    assert PAIR_ALIASES["BTCUSD"] == "XBTUSD"


def test_ticker_for_symbols_maps_errors(monkeypatch):
    client = KrakenPublicClient()

    async def boom(_pairs):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "tickers", boom)
    rows = asyncio.run(client.ticker_for_symbols(["BTCUSD", "ETHUSD"]))
    assert len(rows) == 2
    assert all(isinstance(payload, Exception) for _, payload in rows)


def test_normalize_orderbook_levels_sorts_and_filters():
    bids = normalize_orderbook_levels([["100", "1.5"], ["101", "2"], ["bad", "1"], ["99", "-1"]], reverse=True)
    asks = normalize_orderbook_levels([["102", "0.5"], ["103", "1"]], reverse=False)
    assert bids == [{"price": 101.0, "volume": 2.0}, {"price": 100.0, "volume": 1.5}]
    assert asks == [{"price": 102.0, "volume": 0.5}, {"price": 103.0, "volume": 1.0}]
