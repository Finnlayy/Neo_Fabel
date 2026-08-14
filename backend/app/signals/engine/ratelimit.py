"""Token-bucket rate limiter (monotonic clock; no sleep inside the lock)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucket:
    """Allows up to `rate_per_minute` acquisitions per rolling minute."""

    def __init__(self, rate_per_minute: float, *, now: Callable[[], float] | None = None) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self.capacity = float(rate_per_minute)
        self.tokens = float(rate_per_minute)
        self.rate_per_second = float(rate_per_minute) / 60.0
        self._now = now or time.monotonic
        self._updated = self._now()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self._lock:
            now = self._now()
            elapsed = max(0.0, now - self._updated)
            self._updated = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False
