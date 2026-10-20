"""A rolling 24-hour request budget.

The CountryStateCity free tier is small, so the service refuses to spend more
than a configured number of calls per day and falls back to the open dataset
instead. This is deliberately simple: a monotonic clock, a counter, and a
window start. It is per-process, which is the right scope for a single-worker
development deployment and an honest limitation for anything larger.
"""

from __future__ import annotations

import threading
import time


class DailyQuota:
    """Counts calls against a rolling 24-hour window."""

    def __init__(self, limit: int, *, clock=time.monotonic) -> None:
        self._limit = max(0, limit)
        self._clock = clock
        self._lock = threading.Lock()
        self._window_start = self._clock()
        self._used = 0

    @property
    def limit(self) -> int:
        return self._limit

    def _roll_window(self) -> None:
        now = self._clock()
        if now - self._window_start >= 86_400:
            self._window_start = now
            self._used = 0

    def remaining(self) -> int:
        with self._lock:
            self._roll_window()
            return max(0, self._limit - self._used)

    def exhausted(self) -> bool:
        return self.remaining() <= 0

    def try_consume(self) -> bool:
        """Reserve one call. Returns False when the budget is spent."""
        with self._lock:
            self._roll_window()
            if self._used >= self._limit:
                return False
            self._used += 1
            return True

    def reset(self) -> None:
        with self._lock:
            self._window_start = self._clock()
            self._used = 0
