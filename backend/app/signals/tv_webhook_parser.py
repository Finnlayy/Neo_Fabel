"""Parse TradingView natural webhook JSON → Neo Fabel / Kraken order fields.

TradingView substitutes official placeholders before POST. This module accepts the
resolved JSON (strict Neo schema *or* common natural aliases), rejects leftover
`{{placeholders}}`, and normalizes symbols/sides/sizes into Kraken-ready compact
pairs and plain decimals.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .schemas import TradingViewWebhookBody

_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
_EXCHANGE_PREFIX_RE = re.compile(r"^[A-Z0-9_]+:")

# TV / CEX quote aliases → Neo/Kraken spot quote used by allowlists.
_QUOTE_ALIASES = {
    "USDT": "USD",
    "USDC": "USD",
    "BUSD": "USD",
    "DAI": "USD",
    "ZUSD": "USD",
    "ZEUR": "EUR",
}

# Base aliases → app compact base (Kraken public layer maps BTC→XBT later).
_BASE_ALIASES = {
    "XBT": "BTC",
    "XDG": "DOGE",
    "XXBT": "BTC",
    "XETH": "ETH",
    "XXRP": "XRP",
}

_SIDE_BUY = frozenset({"buy", "long", "enter_long", "open_long", "b", "1"})
_SIDE_SELL = frozenset({"sell", "short", "enter_short", "open_short", "exit_long", "s", "-1"})

_ORDER_MARKET = frozenset({"market", "mkt", "m"})
_ORDER_LIMIT = frozenset({"limit", "lmt", "l"})


class TvWebhookParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None and data[key] != "":
            return data[key]
        # Nested strategy.order.* style flattened keys from some bridges
        flat = key.replace(".", "_")
        if flat in data and data[flat] is not None and data[flat] != "":
            return data[flat]
    return None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        raise TvWebhookParseError("invalid_type", "boolean is not a valid string field")
    return str(value).strip()


def assert_no_unresolved_placeholders(payload: Any, *, path: str = "$") -> None:
    """Fail fast if TradingView did not expand a {{placeholder}}."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_no_unresolved_placeholders(value, path=f"{path}.{key}")
        return
    if isinstance(payload, list):
        for i, value in enumerate(payload):
            assert_no_unresolved_placeholders(value, path=f"{path}[{i}]")
        return
    if isinstance(payload, str) and _PLACEHOLDER_RE.search(payload):
        raise TvWebhookParseError(
            "unresolved_placeholder",
            f"unresolved TradingView placeholder in {path}: {payload!r}",
        )


def normalize_kraken_pair(raw: str) -> str:
    """Map TV/CEX symbols (e.g. COINBASE:BTCUSD, BINANCE:BTCUSDT) → compact Kraken pair."""
    text = raw.strip().upper().replace(" ", "")
    text = text.replace("/", "").replace("-", "").replace("_", "")
    text = _EXCHANGE_PREFIX_RE.sub("", text)
    if not text:
        raise TvWebhookParseError("missing_pair", "pair/symbol is empty")

    # PERP / futures suffixes → spot compact (spot-only pipeline).
    for suffix in ("PERP", "USDT.P", "USD.P"):
        text = text.removesuffix(suffix)

    # Prefer known quote endings (longest first).
    quotes = sorted({*_QUOTE_ALIASES.keys(), "USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"}, key=len, reverse=True)
    base = text
    quote = ""
    for q in quotes:
        if text.endswith(q) and len(text) > len(q):
            base = text[: -len(q)]
            quote = q
            break
    if not quote:
        raise TvWebhookParseError(
            "invalid_pair",
            f"cannot infer quote currency from symbol {raw!r}",
        )

    base = _BASE_ALIASES.get(base, base)
    quote = _QUOTE_ALIASES.get(quote, quote)
    pair = f"{base}{quote}"
    if not pair.isalnum() or len(pair) < 5:
        raise TvWebhookParseError("invalid_pair", f"normalized pair invalid: {pair!r} (from {raw!r})")
    return pair


def normalize_side(raw: Any) -> str:
    text = _as_str(raw).lower().replace(" ", "_")
    if text in _SIDE_BUY:
        return "buy"
    if text in _SIDE_SELL:
        return "sell"
    raise TvWebhookParseError("invalid_side", f"side must be buy/sell (got {raw!r})")


def normalize_order_type(raw: Any | None) -> str:
    if raw is None or _as_str(raw) == "":
        return "market"
    text = _as_str(raw).lower().replace(" ", "_").replace("-", "_")
    if text in _ORDER_MARKET or text in {"strategy.market", "market_order"}:
        return "market"
    if text in _ORDER_LIMIT or text in {"strategy.limit", "limit_order"}:
        return "limit"
    raise TvWebhookParseError("invalid_order_type", f"order_type must be market/limit (got {raw!r})")


def normalize_decimal(raw: Any, *, field: str) -> Decimal:
    if raw is None or raw == "":
        raise TvWebhookParseError("missing_decimal", f"{field} is required")
    if isinstance(raw, bool):
        raise TvWebhookParseError("invalid_decimal", f"{field} must be a number")
    try:
        if isinstance(raw, Decimal):
            value = raw
        elif isinstance(raw, (int, float)):
            # Avoid binary float junk — go through str.
            value = Decimal(str(raw))
        else:
            text = _as_str(raw).replace(",", "")
            if "e" in text.lower():
                raise TvWebhookParseError("invalid_decimal", f"{field} exponent notation is not allowed")
            value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise TvWebhookParseError("invalid_decimal", f"{field} is not a valid decimal: {raw!r}") from exc
    if value.is_nan() or value.is_infinite() or value <= 0:
        raise TvWebhookParseError("invalid_decimal", f"{field} must be a finite positive number")
    # Plain decimal string for Kraken CLI (no exponent).
    plain = format(value, "f")
    if "e" in plain.lower():
        raise TvWebhookParseError("invalid_decimal", f"{field} not Kraken-safe: {plain}")
    return Decimal(plain)


def normalize_occurred_at(raw: Any) -> str:
    text = _as_str(raw)
    if not text:
        raise TvWebhookParseError("missing_occurred_at", "occurred_at/timenow is required")
    # Unix seconds / millis from some bridges
    if text.isdigit():
        from datetime import UTC, datetime

        ts = int(text)
        if ts > 10_000_000_000:  # millis
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if text.endswith(("Z", "z")) or "+" in text[10:]:
        return text if text.endswith("Z") or "+" in text[10:] else text[:-1] + "Z"
    # TV {{time}} / {{timenow}} is yyyy-MM-ddTHH:mm:ssZ — accept bare and force Z
    if "T" in text and len(text) >= 19:
        if text.endswith("Z") or "+" in text[10:]:
            return text
        return text[:19] + "Z"
    raise TvWebhookParseError("invalid_occurred_at", f"cannot parse timestamp {raw!r}")


def to_kraken_order_payload(
    body: TradingViewWebhookBody,
) -> dict[str, str | None]:
    """Canonical argv-friendly fields for Kraken spot order (CLI / API)."""
    return {
        "pair": body.pair,
        "side": body.side,
        "volume": format(body.volume, "f"),
        "ordertype": body.order_type,
        "price": format(body.price, "f") if body.price is not None else None,
        "oflags": None,
        "client_order_id": (body.order_id or body.signal_id)[:64],
    }


def parse_tradingview_natural_webhook(
    payload: dict[str, Any],
    *,
    default_strategy_id: str | None = None,
    default_pair: str | None = None,
) -> TradingViewWebhookBody:
    """Accept strict or natural TV JSON; return validated TradingViewWebhookBody."""
    if not isinstance(payload, dict):
        raise TvWebhookParseError("invalid_payload", "webhook body must be a JSON object")
    assert_no_unresolved_placeholders(payload)

    credential = _as_str(_first(payload, "credential", "secret", "token", "tv_secret", "api_key"))
    if len(credential) < 16:
        raise TvWebhookParseError("missing_credential", "credential/secret missing or too short")

    strategy_id = _as_str(_first(payload, "strategy_id", "strategy", "strategyId", "bot"))
    if not strategy_id and default_strategy_id:
        strategy_id = default_strategy_id
    if not strategy_id:
        raise TvWebhookParseError("missing_strategy_id", "strategy_id is required")

    pair_raw = _first(
        payload,
        "pair",
        "symbol",
        "ticker",
        "market",
        "raw_symbol",
        "tv_symbol",
    )
    if pair_raw is None and default_pair:
        pair = normalize_kraken_pair(default_pair)
        raw_symbol = default_pair
    elif pair_raw is None:
        raise TvWebhookParseError("missing_pair", "pair/symbol/ticker is required")
    else:
        raw_symbol = _as_str(pair_raw)
        # Prefer explicit pair when both pair + ticker present
        explicit_pair = _first(payload, "pair")
        pair = normalize_kraken_pair(_as_str(explicit_pair) if explicit_pair is not None else raw_symbol)

    side = normalize_side(
        _first(payload, "side", "action", "strategy.order.action", "order_action", "direction", "position")
    )
    volume = normalize_decimal(
        _first(
            payload,
            "volume",
            "qty",
            "quantity",
            "size",
            "contracts",
            "strategy.order.contracts",
            "amount",
        ),
        field="volume",
    )
    order_type = normalize_order_type(_first(payload, "order_type", "ordertype", "type", "orderType"))

    price_raw = _first(payload, "price", "limit_price", "strategy.order.price", "order_price")
    price: Decimal | None
    if order_type == "limit":
        if price_raw is None:
            raise TvWebhookParseError("missing_price", "price is required for limit orders")
        price = normalize_decimal(price_raw, field="price")
    elif price_raw is None or price_raw == "" or price_raw == "null":
        price = None
    else:
        price = normalize_decimal(price_raw, field="price")

    observed_raw = _first(payload, "observed_price", "close", "last", "mark_price", "strategy.order.price")
    observed_price = None
    if observed_raw is not None and observed_raw != "" and observed_raw != "null":
        observed_price = normalize_decimal(observed_raw, field="observed_price")

    occurred_at = normalize_occurred_at(
        _first(payload, "occurred_at", "timenow", "time", "timestamp", "fired_at", "alert_time")
    )

    order_id_raw = _first(payload, "order_id", "strategy.order.id", "orderId")
    order_id = _as_str(order_id_raw) if order_id_raw is not None else None
    if order_id == "":
        order_id = None

    signal_id = _as_str(_first(payload, "signal_id", "idempotency_key", "id", "alert_id"))
    if not signal_id:
        if order_id:
            signal_id = f"{order_id}-{occurred_at}"
        else:
            signal_id = f"{pair}-{side}-{occurred_at}-{format(volume, 'f')}"
    if len(signal_id) > 128:
        signal_id = signal_id[:128]

    schema_version = _first(payload, "schema_version", "schemaVersion")
    if schema_version is None:
        schema_version = 1
    try:
        schema_version_int = int(schema_version)
    except (TypeError, ValueError) as exc:
        raise TvWebhookParseError("invalid_schema", "schema_version must be 1") from exc
    if schema_version_int != 1:
        raise TvWebhookParseError("invalid_schema", "schema_version must be 1")

    raw_symbol_out = _as_str(_first(payload, "raw_symbol", "ticker", "symbol")) or raw_symbol
    if len(raw_symbol_out) > 64:
        raw_symbol_out = raw_symbol_out[:64]

    pattern_bias = _first(payload, "pattern_bias", "bias")
    pattern_confidence = _first(payload, "pattern_confidence", "confidence")

    try:
        body = TradingViewWebhookBody(
            schema_version=1,
            credential=credential,
            signal_id=signal_id,
            occurred_at=occurred_at,
            strategy_id=strategy_id,
            pair=pair,
            side=side,  # type: ignore[arg-type]
            volume=volume,
            order_type=order_type,  # type: ignore[arg-type]
            price=price,
            order_id=order_id,
            raw_symbol=raw_symbol_out or None,
            observed_price=observed_price,
            pattern_bias=pattern_bias,  # type: ignore[arg-type]
            pattern_confidence=(
                normalize_decimal(pattern_confidence, field="pattern_confidence")
                if pattern_confidence is not None and pattern_confidence != ""
                else None
            ),
        )
    except Exception as exc:  # pydantic ValidationError etc.
        raise TvWebhookParseError("invalid_payload", f"normalized payload rejected: {exc}") from exc

    return body
