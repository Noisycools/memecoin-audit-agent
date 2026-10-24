from __future__ import annotations

import asyncio
import time


class TokenBucketLimiter:
    """Async token-bucket rate limiter."""

    def __init__(self, rate_per_minute: int) -> None:
        self.rate_per_minute = max(1, rate_per_minute)
        self.capacity = float(self.rate_per_minute)
        self.tokens = float(self.rate_per_minute)
        self.refill_rate = float(self.rate_per_minute) / 60.0
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return

            needed = tokens - self.tokens
            wait_seconds = needed / self.refill_rate
            self.tokens = 0.0
            await asyncio.sleep(wait_seconds)
            self.last_refill = time.monotonic()
