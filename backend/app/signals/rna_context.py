"""In-process RNA blind-pattern context for Fable Engine intake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Literal

PatternBias = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True)
class RnaPatternContext:
    bias: PatternBias
    confidence: Decimal
    symbol: str | None = None
    updated_at: str = ""


_lock = Lock()
_context: RnaPatternContext | None = None


def set_rna_context(
    *,
    bias: PatternBias,
    confidence: Decimal | float | str,
    symbol: str | None = None,
) -> RnaPatternContext:
    global _context
    conf = Decimal(str(confidence))
    ctx = RnaPatternContext(
        bias=bias,
        confidence=conf,
        symbol=symbol.strip().upper() if symbol else None,
        updated_at=datetime.now(UTC).isoformat(),
    )
    with _lock:
        _context = ctx
    return ctx


def get_rna_context() -> RnaPatternContext | None:
    with _lock:
        return _context


def clear_rna_context() -> None:
    global _context
    with _lock:
        _context = None
