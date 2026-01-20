"""Rate limit repository for request throttling.

Contains the abstract RateLimitRepository interface and implementations.
"""

from abc import ABC, abstractmethod
import asyncio
import time


class RateLimitRepository(ABC):
    """Repository for rate limiting counters."""

    @abstractmethod
    async def check_and_increment(
        self, key: str, limit: int, window_seconds: int
    ) -> bool:
        """Check if under limit and increment counter atomically.

        Args:
            key: Rate limit key (e.g., client IP)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            True if request is allowed (under limit)
        """

    @abstractmethod
    async def get_remaining(
        self, key: str, limit: int, window_seconds: int
    ) -> int:
        """Get remaining requests in current window."""


# =============================================================================
# IN-MEMORY IMPLEMENTATION
# =============================================================================


class InMemoryRateLimitRepository(RateLimitRepository):
    """In-memory rate limiter using sliding window."""

    def __init__(self, max_keys: int = 10000):
        self._store: dict[str, list[float]] = {}
        self._max_keys = max_keys
        self._lock = asyncio.Lock()

    async def check_and_increment(
        self, key: str, limit: int, window_seconds: int
    ) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Cleanup if exceeding max keys (evict oldest entries)
            if len(self._store) >= self._max_keys and key not in self._store:
                # Remove oldest 10% of keys
                keys_to_remove = sorted(
                    self._store.keys(),
                    key=lambda k: max(self._store[k]) if self._store[k] else 0
                )[:len(self._store) // 10 + 1]
                for k in keys_to_remove:
                    del self._store[k]

            # Get or create list, filter to current window
            timestamps = self._store.get(key, [])
            timestamps = [t for t in timestamps if t > window_start]

            if len(timestamps) >= limit:
                self._store[key] = timestamps
                return False

            timestamps.append(now)
            self._store[key] = timestamps
            return True

    async def get_remaining(
        self, key: str, limit: int, window_seconds: int
    ) -> int:
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            timestamps = self._store.get(key, [])
            current_count = len([t for t in timestamps if t > window_start])
            return max(0, limit - current_count)
