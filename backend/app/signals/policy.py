"""Deterministic parsing, freshness, pair/size/rate/exposure checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ..models import SignalRoute
from ..settings import Settings
from .domain import CanonicalSignalCandidate, SignalSource


@dataclass(frozen=True)
class PolicyResult:
    ok: bool
    reason_code: str | None = None


def parse_occurred_at(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    return stamp.astimezone(UTC)


def canonical_hash_for(
    *,
    schema_version: int,
    signal_id: str,
    occurred_at: str,
    strategy_id: str,
    pair: str,
    side: str,
    volume: Decimal,
    order_type: str,
    price: Decimal | None,
    order_id: str | None,
    raw_symbol: str | None,
    observed_price: Decimal | None,
    source: SignalSource,
) -> str:
    payload = {
        "schema_version": schema_version,
        "signal_id": signal_id,
        "occurred_at": occurred_at,
        "strategy_id": strategy_id,
        "pair": pair,
        "side": side,
        "volume": format(volume, "f"),
        "order_type": order_type,
        "price": format(price, "f") if price is not None else None,
        "order_id": order_id,
        "raw_symbol": raw_symbol,
        "observed_price": format(observed_price, "f") if observed_price is not None else None,
        "source": source,
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_candidate(
    *,
    schema_version: int,
    signal_id: str,
    occurred_at: str,
    strategy_id: str,
    pair: str,
    side: str,
    volume: Decimal,
    order_type: str,
    price: Decimal | None,
    order_id: str | None,
    raw_symbol: str | None,
    observed_price: Decimal | None,
    source: SignalSource,
) -> CanonicalSignalCandidate:
    digest = canonical_hash_for(
        schema_version=schema_version,
        signal_id=signal_id,
        occurred_at=occurred_at,
        strategy_id=strategy_id,
        pair=pair,
        side=side,
        volume=volume,
        order_type=order_type,
        price=price,
        order_id=order_id,
        raw_symbol=raw_symbol,
        observed_price=observed_price,
        source=source,
    )
    return CanonicalSignalCandidate(
        schema_version=schema_version,
        signal_id=signal_id,
        occurred_at=occurred_at,
        strategy_id=strategy_id,
        pair=pair,
        side=side,  # type: ignore[arg-type]
        volume=volume,
        order_type=order_type,  # type: ignore[arg-type]
        price=price,
        order_id=order_id,
        raw_symbol=raw_symbol,
        observed_price=observed_price,
        source=source,
        canonical_hash=digest,
    )


def check_freshness(occurred_at: datetime, settings: Settings, route: SignalRoute) -> PolicyResult:
    now = datetime.now(UTC)
    age = (now - occurred_at).total_seconds()
    max_age = min(settings.signal_max_age_seconds, route.max_event_age_seconds)
    if age > max_age:
        return PolicyResult(False, "stale_event")
    if age < -settings.signal_future_skew_seconds:
        return PolicyResult(False, "future_skew")
    return PolicyResult(True)


def check_route_policy(candidate: CanonicalSignalCandidate, route: SignalRoute) -> PolicyResult:
    allowlist = {
        part.strip().upper().replace("/", "").replace("-", "")
        for part in route.pair_allowlist.split(",")
        if part.strip()
    }
    if candidate.pair not in allowlist:
        return PolicyResult(False, "pair_not_allowed")
    allowed_types = {part.strip().lower() for part in route.allowed_order_types.split(",") if part.strip()}
    if candidate.order_type not in allowed_types:
        return PolicyResult(False, "order_type_not_allowed")
    if candidate.volume > Decimal(str(route.max_volume)):
        return PolicyResult(False, "volume_cap_exceeded")
    if route.max_notional is not None and candidate.observed_price is not None:
        notional = candidate.volume * candidate.observed_price
        if notional > Decimal(str(route.max_notional)):
            return PolicyResult(False, "notional_cap_exceeded")
    if candidate.strategy_id != route.strategy_id:
        return PolicyResult(False, "strategy_mismatch")
    return PolicyResult(True)


def effective_mode(snapshot: str, current: str) -> str:
    """More restrictive wins: advisory if either is advisory."""
    if snapshot == "advisory" or current == "advisory":
        return "advisory"
    return "bypass_ai"
