"""Kraken public REST helpers used for Windows-safe live tickers."""

import asyncio

from backend.app.integrations.kraken_public import PAIR_ALIASES, KrakenPublicClient


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
