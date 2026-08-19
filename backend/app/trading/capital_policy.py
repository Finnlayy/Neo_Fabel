"""Hard capital policy: no external top-ups, no debt, no negative cash.

The system may only trade with balances already on Kraken. It must never
invoke deposit / withdraw / transfer / funding flows, and must never place
orders that would borrow margin or drive cash below zero.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from backend.app.trading.guardrails import GuardrailViolation

# CLI command heads / tokens that move capital in or out of the exchange wallet.
FORBIDDEN_CAPITAL_COMMANDS = frozenset(
    {
        "deposit",
        "withdraw",
        "withdrawal",
        "transfer",
        "funding",
        "earn",
        "stake",
        "unstake",
        "receive",
        "send",
        "address",  # deposit address generation — external replenish path
    }
)

# Fiat / stable cash keys (EUR accounts count ZEUR; USD accounts ZUSD).
CASH_KEYS = ("ZUSD", "USD", "ZEUR", "EUR", "USDT", "USDC")


def _d(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def assert_args_forbid_external_capital(args: list[str]) -> None:
    """Raise if a Kraken CLI argv would recharge or move capital outside trading."""
    tokens = {str(a).strip().lower() for a in args if a}
    hit = tokens & FORBIDDEN_CAPITAL_COMMANDS
    if hit:
        raise GuardrailViolation(
            "external_capital_forbidden",
            f"capital ops blocked ({', '.join(sorted(hit))}): system may not replenish or move funds from outside Kraken",
        )


def _iter_balance_maps(balance_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not balance_payload or not isinstance(balance_payload, dict):
        return []
    sources: list[dict[str, Any]] = [balance_payload]
    nested = balance_payload.get("result") or balance_payload.get("balances")
    if isinstance(nested, dict):
        sources.append(nested)
    return sources


def cash_balance_quote(balance_payload: dict[str, Any] | None) -> Decimal:
    """Sum free cash (USD + EUR + stables). Nested duplicates are de-duped by key."""
    merged: dict[str, Decimal] = {}
    for src in _iter_balance_maps(balance_payload):
        for key in CASH_KEYS:
            if key in src:
                merged[key] = _d(src.get(key))
    return sum(merged.values(), Decimal(0))


# Back-compat alias used by older call sites / tests.
cash_balance_usd = cash_balance_quote


def asset_balance(balance_payload: dict[str, Any] | None, asset: str) -> Decimal:
    if not balance_payload or not isinstance(balance_payload, dict):
        return Decimal(0)
    want = asset.strip().upper()
    aliases = {want, want.lstrip("X"), f"X{want}" if not want.startswith("X") else want}
    if want == "BTC":
        aliases |= {"XBT", "XXBT"}
    if want == "XBT":
        aliases |= {"BTC", "XXBT"}
    best = Decimal(0)
    for src in _iter_balance_maps(balance_payload):
        for key, value in src.items():
            if str(key).upper() in aliases:
                vol = _d(value)
                best = max(best, vol)
    return best


def base_asset_from_pair(pair: str) -> str:
    normalized = pair.strip().upper().replace("/", "").replace("-", "")
    for quote in ("USDT", "USDC", "USD", "EUR", "GBP"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            return normalized[: -len(quote)]
    return normalized


def assert_no_debt_leverage(*, leverage: int | None, market_type: str, reduce_only: bool = False) -> None:
    """Forbid borrowed capital: spot leverage must be 1; futures only reduce-only."""
    mt = (market_type or "spot").lower()
    if mt == "futures" and not reduce_only:
        raise GuardrailViolation(
            "debt_forbidden",
            "futures opens are blocked — no debt/margin; use reduce-only closes only",
        )
    lev = int(leverage or 1)
    if lev > 1:
        raise GuardrailViolation(
            "debt_forbidden",
            f"leverage {lev}x blocked — system may not borrow; leverage must be 1",
        )


def assert_non_negative_cash(cash: Decimal) -> None:
    if cash < 0:
        raise GuardrailViolation(
            "negative_cash_forbidden",
            f"cash balance {cash} is below 0 — trading halted until non-negative",
        )


def assert_max_notional(
    *,
    volume: Decimal,
    price: Decimal | None,
    max_notional: Decimal,
    side: Literal["buy", "sell"] = "buy",
) -> None:
    """Cap quote notional per new trade (for tiny accounts, e.g. max €2)."""
    if max_notional <= 0:
        return
    if price is None or price <= 0:
        if side == "buy":
            raise GuardrailViolation(
                "notional_unknown",
                "market buy needs a price estimate to enforce max notional — provide limit price or wait for ticker",
            )
        return
    notional = volume * price
    if notional > max_notional:
        raise GuardrailViolation(
            "max_notional",
            f"notional {notional} exceeds max_notional {max_notional} per trade",
        )


def assert_buy_affordable(
    *,
    cash: Decimal,
    volume: Decimal,
    price: Decimal | None,
    fee_buffer: Decimal = Decimal("0.002"),
) -> None:
    """Reject buys that would spend more cash than available (no overdraft/debt)."""
    assert_non_negative_cash(cash)
    if volume <= 0:
        raise GuardrailViolation("invalid_size", "order volume must be positive")
    if price is None or price <= 0:
        if cash <= 0:
            raise GuardrailViolation(
                "insufficient_cash",
                "no cash available for market buy — cannot go below 0 or create debt",
            )
        return
    cost = volume * price
    cost_with_fee = cost * (Decimal(1) + fee_buffer)
    if cost_with_fee > cash:
        raise GuardrailViolation(
            "insufficient_cash",
            f"buy cost {cost_with_fee} exceeds cash {cash} — no external replenish, no debt",
        )


def assert_sell_covered(*, held: Decimal, volume: Decimal) -> None:
    """Reject sells larger than free inventory (no short / borrowed sell)."""
    if volume <= 0:
        raise GuardrailViolation("invalid_size", "order volume must be positive")
    if volume > held:
        raise GuardrailViolation(
            "insufficient_inventory",
            f"sell volume {volume} exceeds held {held} — shorting/debt forbidden",
        )


def assert_live_order_capital(
    *,
    side: Literal["buy", "sell"],
    pair: str,
    volume: Decimal,
    price: Decimal | None,
    balance_payload: dict[str, Any] | None,
    market_type: str = "spot",
    leverage: int = 1,
    reduce_only: bool = False,
    max_notional: Decimal | None = None,
) -> None:
    assert_no_debt_leverage(leverage=leverage, market_type=market_type, reduce_only=reduce_only)
    cash = cash_balance_quote(balance_payload)
    assert_non_negative_cash(cash)
    if max_notional is not None:
        assert_max_notional(volume=volume, price=price, max_notional=max_notional, side=side)
    if side == "buy":
        if market_type == "futures" and reduce_only:
            return
        assert_buy_affordable(cash=cash, volume=volume, price=price)
    else:
        base = base_asset_from_pair(pair)
        held = asset_balance(balance_payload, base)
        if market_type == "futures" and reduce_only:
            return
        assert_sell_covered(held=held, volume=volume)
