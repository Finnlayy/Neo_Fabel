"""Kraken public REST market data (no API keys, works without the CLI)."""

from __future__ import annotations

from typing import Any

import httpx

from .kraken_cli import KrakenCliError

# App uses BTCUSD-style symbols; Kraken public API prefers XBT for bitcoin.
PAIR_ALIASES = {
    "BTCUSD": "XBTUSD",
    "BTC/USD": "XBTUSD",
    "XBTUSD": "XBTUSD",
    "ETHUSD": "ETHUSD",
    "MATICUSD": "POLUSD",  # MATIC rebranded to POL on Kraken
}


class KrakenPublicClient:
    def __init__(self, *, base_url: str = "https://api.kraken.com", timeout_seconds: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _pair(self, pair: str) -> str:
        normalized = pair.strip().upper().replace("/", "").replace("-", "")
        return PAIR_ALIASES.get(normalized, normalized)

    async def ticker(self, pair: str) -> dict[str, Any]:
        results = await self.tickers([pair])
        key = next(iter(results), None)
        if key is None:
            raise KrakenCliError("api", f"no ticker data for {pair}")
        return results[key]

    async def tickers(self, pairs: list[str]) -> dict[str, dict[str, Any]]:
        if not pairs:
            return {}
        mapped = list(dict.fromkeys(self._pair(pair) for pair in pairs))
        try:
            return await self._fetch_ticker_query(",".join(mapped))
        except KrakenCliError as exc:
            # One unknown pair fails the whole multi-pair query — fall back per symbol.
            if "Unknown asset pair" not in str(exc) or len(mapped) <= 1:
                raise
            merged: dict[str, dict[str, Any]] = {}
            for pair in mapped:
                try:
                    merged.update(await self._fetch_ticker_query(pair))
                except KrakenCliError:
                    continue
            if not merged:
                raise
            return merged

    async def _fetch_ticker_query(self, query: str) -> dict[str, dict[str, Any]]:
        url = f"{self.base_url}/0/public/Ticker"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params={"pair": query})
        except httpx.TimeoutException as exc:
            raise KrakenCliError("network", "kraken public ticker timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise KrakenCliError("network", f"kraken public ticker failed: {exc}", retryable=True) from exc

        if response.status_code >= 400:
            raise KrakenCliError("api", f"kraken public HTTP {response.status_code}")

        payload = response.json()
        errors = payload.get("error") if isinstance(payload, dict) else None
        if errors:
            raise KrakenCliError("api", f"kraken public error: {errors}")
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise KrakenCliError("parse", "kraken public ticker returned unexpected payload")

        normalized: dict[str, dict[str, Any]] = {}
        for key, value in result.items():
            if not isinstance(value, dict):
                continue
            close = value.get("c")
            open_ = value.get("o")
            last = close[0] if isinstance(close, list) and close else close
            entry = dict(value)
            entry["last"] = last
            entry["price"] = last
            entry["close"] = last
            entry["open"] = open_
            normalized[str(key)] = entry
        return normalized

    async def ticker_for_symbols(self, symbols: list[str]) -> list[tuple[str, dict[str, Any] | Exception]]:
        """Return (requested_symbol, data|error) preserving request order."""
        try:
            bulk = await self.tickers(symbols)
        except Exception as exc:  # noqa: BLE001 — per-symbol fallback below
            return [(symbol, exc) for symbol in symbols]

        out: list[tuple[str, dict[str, Any] | Exception]] = []
        by_upper = {key.upper(): value for key, value in bulk.items()}
        for symbol in symbols:
            mapped = self._pair(symbol)
            match = _match_ticker(by_upper, mapped)
            if match is None:
                out.append((symbol, KrakenCliError("api", f"ticker missing for {symbol}")))
            else:
                out.append((symbol, match))
        return out

    async def orderbook(self, pair: str, *, count: int = 25) -> dict[str, Any]:
        """Fetch public L2 depth and return normalized bids/asks."""
        depth = max(1, min(int(count), 100))
        mapped = self._pair(pair)
        url = f"{self.base_url}/0/public/Depth"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params={"pair": mapped, "count": depth})
        except httpx.TimeoutException as exc:
            raise KrakenCliError("network", "kraken public orderbook timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise KrakenCliError("network", f"kraken public orderbook failed: {exc}", retryable=True) from exc

        if response.status_code >= 400:
            raise KrakenCliError("api", f"kraken public HTTP {response.status_code}")

        payload = response.json()
        errors = payload.get("error") if isinstance(payload, dict) else None
        if errors:
            raise KrakenCliError("api", f"kraken public error: {errors}")
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict) or not result:
            raise KrakenCliError("parse", "kraken public orderbook returned unexpected payload")

        by_upper = {str(key).upper(): value for key, value in result.items() if isinstance(value, dict)}
        book = _match_ticker(by_upper, mapped)
        if book is None:
            book = next(iter(by_upper.values()), None)
        if not isinstance(book, dict):
            raise KrakenCliError("api", f"no orderbook data for {pair}")

        return {
            "pair": pair.strip().upper().replace("/", "").replace("-", ""),
            "bids": normalize_orderbook_levels(book.get("bids"), reverse=True),
            "asks": normalize_orderbook_levels(book.get("asks"), reverse=False),
        }


def _match_ticker(by_upper: dict[str, dict[str, Any]], mapped: str) -> dict[str, Any] | None:
    if mapped in by_upper:
        return by_upper[mapped]
    # Kraken often returns alt names: XXBTZUSD, XETHZUSD, XXRPZUSD.
    special = {
        "XBTUSD": ("XXBTZUSD", "XBTUSD", "XBTZUSD"),
        "ETHUSD": ("XETHZUSD", "ETHUSD", "ETHZUSD"),
        "XRPUSD": ("XXRPZUSD", "XRPUSD"),
        "POLUSD": ("POLUSD", "MATICUSD"),
    }
    for candidate in special.get(mapped, ()):
        if candidate in by_upper:
            return by_upper[candidate]
    base = mapped.replace("USD", "")
    for key, value in by_upper.items():
        if base and base in key and key.endswith("USD"):
            return value
    return None


def normalize_orderbook_levels(raw: Any, *, reverse: bool) -> list[dict[str, float]]:
    if not isinstance(raw, list):
        return []
    levels: list[dict[str, float]] = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            price = float(row[0])
            volume = float(row[1])
        except (TypeError, ValueError):
            continue
        if price <= 0 or volume < 0:
            continue
        levels.append({"price": price, "volume": volume})
    levels.sort(key=lambda item: item["price"], reverse=reverse)
    return levels
