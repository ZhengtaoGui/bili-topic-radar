from __future__ import annotations

import asyncio
import random
import time


class AsyncRateLimiter:
    def __init__(self, min_delay: float = 1.5, max_delay: float = 2.0) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = random.uniform(self.min_delay, self.max_delay)
            sleep_for = self._last_request_at + delay - now
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_request_at = time.monotonic()
