"""Spot vs futures instrument identity — shared across paper, signals, and market data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

MarketType = Literal["spot", "futures"]

# Kraken linear perp symbols (PF_) — extend as needed.
SPOT_TO_FUTURES: dict[str, str] = {
    "BTCUSD": "PF_XBTUSD",
    "XBTUSD": "PF_XBTUSD",
    "ETHUSD": "PF_ETHUSD",
    "SOLUSD": "PF_SOLUSD",
    "XRPUSD": "PF_XRPUSD",
    "ADAUSD": "PF_ADAUSD",
    "DOTUSD": "PF_DOTUSD",
    "LINKUSD": "PF_LINKUSD",
    "LTCUSD": "PF_LTCUSD",
    "MATICUSD": "PF_POLUSD",
    "POLUSD": "PF_POLUSD",
    "AVAXUSD": "PF_AVAXUSD",
    "BCHUSD": "PF_BCHUSD",
}

FUTURES_PREFIXES = ("PF_", "PI_", "FI_")

# Spot aliases (Kraken uses XBT for BTC).
SPOT_ALIASES: dict[str, str] = {
    "BTC/USD": "BTCUSD",
    "XBT/USD": "BTCUSD",
    "XBTUSD": "BTCUSD",
    "MATIC/USD": "MATICUSD",
    "POL/USD": "POLUSD",
}


@dataclass(frozen=True)
class Instrument:
    market_type: MarketType
    symbol: str
    canonical_id: str
    quote: str = "USD"
    contract_size: Decimal = Decimal(1)

    def price_key(self) -> str:
        """Key for mark-price maps (includes market type)."""
        return self.canonical_id


def normalize_symbol(raw: str, *, market_type: MarketType = "spot") -> str:
    text = raw.strip().upper().replace("/", "").replace("-", "")
    if market_type == "spot":
        return SPOT_ALIASES.get(raw.strip().upper(), SPOT_ALIASES.get(text, text))
    return text


def is_futures_symbol(symbol: str) -> bool:
    upper = symbol.strip().upper()
    return upper.startswith(FUTURES_PREFIXES)


def futures_symbol_for_spot(spot_symbol: str) -> str:
    norm = normalize_symbol(spot_symbol, market_type="spot")
    mapped = SPOT_TO_FUTURES.get(norm)
    if mapped:
        return mapped
    if is_futures_symbol(norm):
        return norm
    return f"PF_{norm}"


def resolve_instrument(
    market_type: MarketType,
    raw_symbol: str,
    *,
    leverage: int = 1,
) -> Instrument:
    if market_type not in {"spot", "futures"}:
        raise ValueError(f"unsupported market_type: {market_type}")

    if market_type == "spot":
        symbol = normalize_symbol(raw_symbol, market_type="spot")
        if is_futures_symbol(symbol):
            raise ValueError(f"futures symbol {symbol} cannot be used as spot")
        return Instrument(
            market_type="spot",
            symbol=symbol,
            canonical_id=f"spot:{symbol}",
        )

    symbol = normalize_symbol(raw_symbol, market_type="futures")
    if not is_futures_symbol(symbol):
        symbol = futures_symbol_for_spot(symbol)
    int(leverage)
    return Instrument(
        market_type="futures",
        symbol=symbol,
        canonical_id=f"futures:{symbol}",
        contract_size=Decimal(1),
    )
