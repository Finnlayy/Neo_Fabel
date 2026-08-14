"""Immutable signal domain types, enums, and legal state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

SignalMode = Literal["bypass_ai", "advisory"]
ExecutionTarget = Literal["kraken_paper"]
SignalSource = Literal["tradingview", "mcp", "fable_engine"]
CredentialKind = Literal["tradingview_secret", "mcp_bearer"]
JobStatus = Literal["ready", "leased", "retry_wait", "complete", "dead"]
AdvisoryDecision = Literal["approve", "reject", "abstain", "timeout", "error"]

EventStatus = Literal[
    "received",
    "queued",
    "validating",
    "rejected_validation",
    "rejected_guardrail",
    "evaluating_advisory",
    "rejected_advisory",
    "failed_closed",
    "approved",
    "bypass_approved",
    "paper_submitting",
    "paper_accepted",
    "paper_failed",
    "execution_unknown",
    "dry_run_recorded",
]

LEGAL_TRANSITIONS: dict[EventStatus, frozenset[EventStatus]] = {
    "received": frozenset({"queued"}),
    "queued": frozenset({"validating"}),
    "validating": frozenset(
        {
            "rejected_validation",
            "rejected_guardrail",
            "evaluating_advisory",
            "bypass_approved",
            "failed_closed",
        }
    ),
    "evaluating_advisory": frozenset({"rejected_advisory", "failed_closed", "approved"}),
    "approved": frozenset({"paper_submitting", "dry_run_recorded"}),
    "bypass_approved": frozenset({"paper_submitting", "dry_run_recorded"}),
    "paper_submitting": frozenset({"paper_accepted", "paper_failed", "execution_unknown"}),
    "dry_run_recorded": frozenset(),
    "rejected_validation": frozenset(),
    "rejected_guardrail": frozenset(),
    "rejected_advisory": frozenset(),
    "failed_closed": frozenset(),
    "paper_accepted": frozenset(),
    "paper_failed": frozenset(),
    "execution_unknown": frozenset(),
}


@dataclass(frozen=True)
class CanonicalSignalCandidate:
    schema_version: int
    signal_id: str
    occurred_at: str
    strategy_id: str
    pair: str
    side: Literal["buy", "sell"]
    volume: Decimal
    order_type: Literal["market", "limit"]
    price: Decimal | None
    order_id: str | None
    raw_symbol: str | None
    observed_price: Decimal | None
    source: SignalSource
    canonical_hash: str
    # Optional RNA blind-pattern context; kept out of core routing/pair policy unless provided.
    pattern_bias: Literal["bullish", "bearish", "neutral"] | None = None
    pattern_confidence: Decimal | None = None

    def to_policy_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "signal_id": self.signal_id,
            "occurred_at": self.occurred_at,
            "strategy_id": self.strategy_id,
            "pair": self.pair,
            "side": self.side,
            "volume": format(self.volume, "f"),
            "order_type": self.order_type,
            "price": format(self.price, "f") if self.price is not None else None,
            "order_id": self.order_id,
            "raw_symbol": self.raw_symbol,
            "observed_price": format(self.observed_price, "f") if self.observed_price is not None else None,
            "source": self.source,
            "canonical_hash": self.canonical_hash,
            "pattern_bias": self.pattern_bias,
            "pattern_confidence": format(self.pattern_confidence, "f") if self.pattern_confidence is not None else None,
        }


def assert_transition(current: EventStatus, nxt: EventStatus) -> None:
    allowed = LEGAL_TRANSITIONS.get(current, frozenset())
    if nxt not in allowed:
        raise ValueError(f"illegal transition {current} -> {nxt}")
