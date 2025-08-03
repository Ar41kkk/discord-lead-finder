# src/dkh/application/utils.py
import asyncio

import structlog

logger = structlog.get_logger(__name__)


class SimpleGlobalRateLimiter:
    """
    Простий глобальний обмежувач швидкості, як у вашому оригінальному коді.
    """

    def __init__(self, interval: float):
        self._interval = interval
        self._next_available_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            if now < self._next_available_time:
                sleep_duration = self._next_available_time - now
                logger.debug('Global rate limiter: sleeping', duration_s=round(sleep_duration, 2))
                await asyncio.sleep(sleep_duration)
            self._next_available_time = asyncio.get_event_loop().time() + self._interval
