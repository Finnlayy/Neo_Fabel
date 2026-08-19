"""Deterministic parsing, freshness, pair/size/rate/exposure checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast

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


def _canon_decimal(value: Decimal | None) -> str | None:
    """Stable decimal text across NUMERIC round-trips (Postgres pads scale zeros)."""
    if value is None:
        return None
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text else "0"


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
    pattern_bias: str | None = None,
    pattern_confidence: Decimal | None = None,
) -> str:
    payload = {
        "schema_version": schema_version,
        "signal_id": signal_id,
        "occurred_at": occurred_at,
        "strategy_id": strategy_id,
        "pair": pair,
        "side": side,
        "volume": _canon_decimal(volume),
        "order_type": order_type,
        "price": _canon_decimal(price),
        "order_id": order_id,
        "raw_symbol": raw_symbol,
        "observed_price": _canon_decimal(observed_price),
        "source": source,
    }
    if pattern_bias is not None:
        payload["pattern_bias"] = pattern_bias
    if pattern_confidence is not None:
        payload["pattern_confidence"] = _canon_decimal(pattern_confidence)
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
    pattern_bias: str | None = None,
    pattern_confidence: Decimal | None = None,
) -> CanonicalSignalCandidate:
    if pattern_bias not in {None, "bullish", "bearish", "neutral"}:
        raise ValueError("pattern_bias must be bullish, bearish, neutral, or null")
    canonical_pattern_bias = cast(
        Literal["bullish", "bearish", "neutral"] | None,
        pattern_bias,
    )
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
        pattern_bias=canonical_pattern_bias,
        pattern_confidence=pattern_confidence,
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
        pattern_bias=canonical_pattern_bias,
        pattern_confidence=pattern_confidence,
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


# Event statuses that count toward route open exposure (paper fills + in-flight).
OPEN_EXPOSURE_STATUSES: frozenset[str] = frozenset(
    {
        "approved",
        "bypass_approved",
        "paper_submitting",
        "paper_accepted",
        "execution_unknown",
    }
)


def check_route_policy(
    candidate: CanonicalSignalCandidate,
    route: SignalRoute,
    *,
    allow_all_pairs: bool = False,
    current_open_exposure: Decimal | None = None,
) -> PolicyResult:
    allowlist = {
        part.strip().upper().replace("/", "").replace("-", "")
        for part in route.pair_allowlist.split(",")
        if part.strip()
    }
    # Paper (or explicit *) may trade any symbol; live keep routes tight.
    if (
        not allow_all_pairs
        and "*" not in allowlist
        and "ALL" not in allowlist
        and candidate.pair not in allowlist
    ):
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
    exposure = check_open_exposure(
        candidate,
        route,
        current_open_exposure=current_open_exposure if current_open_exposure is not None else Decimal(0),
    )
    if not exposure.ok:
        return exposure
    return PolicyResult(True)


def check_open_exposure(
    candidate: CanonicalSignalCandidate,
    route: SignalRoute,
    *,
    current_open_exposure: Decimal,
) -> PolicyResult:
    """Enforce ``max_open_exposure`` when set (None = uncapped). Buys only; paper-safe."""
    cap = getattr(route, "max_open_exposure", None)
    if cap is None:
        return PolicyResult(True)
    if candidate.side != "buy":
        return PolicyResult(True)
    projected = Decimal(str(current_open_exposure)) + candidate.volume
    if projected > Decimal(str(cap)):
        return PolicyResult(False, "open_exposure_cap_exceeded")
    return PolicyResult(True)


def effective_mode(snapshot: str, current: str) -> str:
    """More restrictive wins: advisory if either is advisory."""
    if snapshot == "advisory" or current == "advisory":
        return "advisory"
    return "bypass_ai"
