"""Monotonic, cancellation-safe request spacing within one asyncio event loop."""

import asyncio
import math
import time
from types import TracebackType


class AsyncRateLimiter:
    """Space admissions without bursts; share an instance across concurrent SEC tasks."""

    def __init__(self, rate_limit_per_sec: float) -> None:
        """Validate the SEC rate cap and initialize serialized admission state."""
        if not math.isfinite(rate_limit_per_sec) or not 0 < rate_limit_per_sec <= 10:
            raise ValueError("rate_limit_per_sec must be finite and > 0 and <= 10")
        self.min_interval = 1.0 / rate_limit_per_sec
        self._lock = asyncio.Lock()
        self._last_request_time: float | None = None

    async def acquire(self) -> float:
        """Admit one request, returning seconds actually spent sleeping inside the lock."""
        async with self._lock:
            slept = 0.0
            if self._last_request_time is not None:
                remaining = self.min_interval - (time.monotonic() - self._last_request_time)
                while remaining > 0:
                    started = time.monotonic()
                    await asyncio.sleep(remaining)
                    slept += time.monotonic() - started
                    remaining = self.min_interval - (time.monotonic() - self._last_request_time)
            self._last_request_time = time.monotonic()
            return slept

    async def __aenter__(self) -> "AsyncRateLimiter":
        """Acquire an admission for an async context."""
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Leave the context without suppressing exceptions or releasing rate credit."""
