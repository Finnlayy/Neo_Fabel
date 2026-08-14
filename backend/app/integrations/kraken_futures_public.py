"""Kraken Futures public REST (read-only tickers for paper marks)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from backend.app.integrations.kraken_cli import KrakenCliError


class KrakenFuturesPublicClient:
    def __init__(
        self,
        *,
        base_url: str = "https://futures.kraken.com/derivatives/api/v3",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def ticker(self, symbol: str) -> dict[str, Any]:
        sym = symbol.strip().upper()
        url = f"{self.base_url}/tickers"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params={"symbol": sym})
        except httpx.TimeoutException as exc:
            raise KrakenCliError("network", "kraken futures ticker timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise KrakenCliError("network", f"kraken futures ticker failed: {exc}", retryable=True) from exc

        if response.status_code >= 400:
            raise KrakenCliError("api", f"kraken futures HTTP {response.status_code}")

        payload = response.json()
        tickers = payload.get("tickers") if isinstance(payload, dict) else None
        if not isinstance(tickers, list):
            raise KrakenCliError("parse", "kraken futures unexpected ticker payload")

        for row in tickers:
            if not isinstance(row, dict):
                continue
            if str(row.get("symbol", "")).upper() == sym:
                last = row.get("last") or row.get("markPrice") or row.get("indexPrice")
                return {
                    "symbol": sym,
                    "last": str(last),
                    "price": str(last),
                    "source": "kraken-futures-public",
                }
        raise KrakenCliError("api", f"no futures ticker for {sym}")

    async def last_price(self, symbol: str) -> Decimal:
        data = await self.ticker(symbol)
        price = Decimal(str(data.get("last") or data.get("price") or "0"))
        if price <= 0:
            raise KrakenCliError("api", f"invalid futures price for {symbol}")
        return price
