from __future__ import annotations

import time


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def allow(self, *, scope: str, identifier: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0

        now = time.monotonic()
        key = (scope, identifier)
        window_started_at, count = self._buckets.get(key, (now, 0))
        elapsed = now - window_started_at

        if elapsed >= window_seconds:
            self._buckets[key] = (now, 1)
            return True, 0

        if count >= limit:
            retry_after = max(1, int(window_seconds - elapsed))
            return False, retry_after

        self._buckets[key] = (window_started_at, count + 1)
        return True, 0

    def reset(self) -> None:
        self._buckets.clear()
