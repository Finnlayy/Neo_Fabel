from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Lock


class GuardrailViolation(ValueError):
    """Raised when an order would breach configured Level 4 limits."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TradingGuardrails:
    """Position and frequency limits the CLI does not enforce."""

    max_order_size: Decimal = Decimal("0.01")
    max_notional: Decimal = Decimal(2)
    max_open_positions: int = 3
    max_trades_per_hour: int = 10
    min_trade_interval_seconds: float = 30.0
    pair_allowlist: frozenset[str] = frozenset({"ADAUSD", "XRPUSD", "ADAEUR", "XRPEUR"})

    def assert_pair_allowed(self, pair: str) -> str:
        normalized = pair.strip().upper().replace("/", "").replace("-", "")
        # Live guardrails never honor * / ALL — that bypass is paper-only via PAPER_ALLOW_ALL_PAIRS.
        if not self.pair_allowlist:
            raise GuardrailViolation(
                "pair_allowlist_empty",
                "live pair allowlist is empty — refuse all pairs",
            )
        if "*" in self.pair_allowlist or "ALL" in self.pair_allowlist:
            raise GuardrailViolation(
                "pair_allowlist_wildcard_forbidden",
                "wildcard pair allowlist is not permitted on live guardrails",
            )
        if normalized not in self.pair_allowlist:
            raise GuardrailViolation(
                "pair_not_allowed",
                f"pair {normalized} is outside the allowlist",
            )
        return normalized

    def assert_order_size(self, volume: Decimal) -> None:
        if volume <= 0:
            raise GuardrailViolation("invalid_size", "order volume must be positive")
        if volume > self.max_order_size:
            raise GuardrailViolation(
                "max_order_size",
                f"volume {volume} exceeds max_order_size {self.max_order_size}",
            )

    def assert_open_capacity(self, open_positions: int) -> None:
        if open_positions >= self.max_open_positions:
            raise GuardrailViolation(
                "max_open_positions",
                f"open positions {open_positions} at max_open_positions {self.max_open_positions}",
            )

    def check_order(self, *, pair: str, volume: Decimal, open_positions: int) -> str:
        normalized = self.assert_pair_allowed(pair)
        self.assert_order_size(volume)
        self.assert_open_capacity(open_positions)
        return normalized


@dataclass
class TradeRateLimiter:
    """Sliding-window trade counter plus minimum spacing between trades."""

    max_trades_per_hour: int
    min_interval_seconds: float = 30.0
    _timestamps: deque[datetime] = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)

    def assert_can_trade(self, now: datetime | None = None) -> None:
        stamp = now or datetime.now(UTC)
        window_start = stamp - timedelta(hours=1)
        with self._lock:
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()
            if self._timestamps and self.min_interval_seconds > 0:
                elapsed = (stamp - self._timestamps[-1]).total_seconds()
                if elapsed < self.min_interval_seconds:
                    wait = self.min_interval_seconds - elapsed
                    raise GuardrailViolation(
                        "min_trade_interval",
                        f"wait {wait:.1f}s — max 1 new trade every {self.min_interval_seconds:g}s",
                    )
            if len(self._timestamps) >= self.max_trades_per_hour:
                raise GuardrailViolation(
                    "max_trades_per_hour",
                    f"already placed {len(self._timestamps)} trades in the last hour",
                )

    def record_trade(self, now: datetime | None = None) -> None:
        stamp = now or datetime.now(UTC)
        with self._lock:
            self._timestamps.append(stamp)

    def trades_in_window(self, now: datetime | None = None) -> int:
        stamp = now or datetime.now(UTC)
        window_start = stamp - timedelta(hours=1)
        with self._lock:
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()
            return len(self._timestamps)
