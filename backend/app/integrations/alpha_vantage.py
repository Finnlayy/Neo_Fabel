import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


class AlphaVantageError(RuntimeError):
    def __init__(self, category: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class AlphaVantageClient:
    api_key: str | None
    base_url: str = "https://www.alphavantage.co/query"
    timeout_seconds: float = 15.0

    async def _get(self, params: dict[str, str]) -> dict[str, Any]:
        if not self.api_key:
            raise AlphaVantageError("config", "ALPHAVANTAGE_API_KEY is not configured")
        request_params = {**params, "apikey": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(self.base_url, params=request_params)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AlphaVantageError("network", "Alpha Vantage request timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AlphaVantageError("network", "Alpha Vantage request failed", retryable=True) from exc
        except ValueError as exc:
            raise AlphaVantageError("parse", "Alpha Vantage returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise AlphaVantageError("parse", "Alpha Vantage returned a non-object response")
        if "Error Message" in payload:
            raise AlphaVantageError("api", "Alpha Vantage rejected the request")
        if "Note" in payload or "Information" in payload:
            raise AlphaVantageError("rate_limit", "Alpha Vantage rate limit or entitlement limit reached", retryable=True)
        return payload

    async def equity_bulk(self, symbols: list[str]) -> dict[str, Any]:
        if not 1 <= len(symbols) <= 100:
            raise AlphaVantageError("validation", "bulk equity quotes accept 1 to 100 symbols")
        return await self._get({"function": "REALTIME_BULK_QUOTES", "symbol": ",".join(symbols)})

    async def equity_quote(self, symbol: str) -> dict[str, Any]:
        return await self._get({"function": "GLOBAL_QUOTE", "symbol": symbol})

    async def forex_quote(self, pair: str) -> dict[str, Any]:
        if len(pair) != 6:
            raise AlphaVantageError("validation", "forex symbols must contain six currency letters")
        return await self._get(
            {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": pair[:3],
                "to_currency": pair[3:],
            }
        )

    async def intraday(self, asset_class: str, symbol: str, interval: str) -> dict[str, Any]:
        if interval not in {"1min", "5min", "15min", "30min", "60min"}:
            raise AlphaVantageError("validation", "unsupported intraday interval")
        if asset_class == "sp500":
            return await self._get(
                {
                    "function": "TIME_SERIES_INTRADAY",
                    "symbol": symbol,
                    "interval": interval,
                    "outputsize": "compact",
                }
            )
        if asset_class == "forex":
            if len(symbol) != 6:
                raise AlphaVantageError("validation", "forex symbols must contain six currency letters")
            return await self._get(
                {
                    "function": "FX_INTRADAY",
                    "from_symbol": symbol[:3],
                    "to_symbol": symbol[3:],
                    "interval": interval,
                    "outputsize": "compact",
                }
            )
        if asset_class == "crypto":
            if len(symbol) < 6:
                raise AlphaVantageError("validation", "crypto symbols must contain a base and quote currency")
            return await self._get(
                {
                    "function": "CRYPTO_INTRADAY",
                    "symbol": symbol[:-3],
                    "market": symbol[-3:],
                    "interval": interval,
                    "outputsize": "compact",
                }
            )
        raise AlphaVantageError("validation", "unsupported asset class")

    async def forex_batch(self, pairs: list[str], concurrency: int = 2) -> list[tuple[str, dict[str, Any] | Exception]]:
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def fetch(pair: str) -> tuple[str, dict[str, Any] | Exception]:
            async with semaphore:
                try:
                    return pair, await self.forex_quote(pair)
                except Exception as exc:  # Preserve per-symbol failures in a batch response.
                    return pair, exc

        return list(await asyncio.gather(*(fetch(pair) for pair in pairs)))
