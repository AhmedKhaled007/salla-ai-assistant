"""State repository for OAuth CSRF state parameters.

Contains the abstract StateRepository interface and implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import asyncio


class StateRepository(ABC):
    """Repository for OAuth CSRF state parameters."""

    @abstractmethod
    async def store(self, state: str, ttl_seconds: int = 600) -> None:
        """Store state with TTL (default 10 min)."""

    @abstractmethod
    async def validate_and_consume(self, state: str) -> bool:
        """Validate state exists and delete it atomically.

        Returns:
            True if state was valid (existed and not expired)
        """


# =============================================================================
# IN-MEMORY IMPLEMENTATION
# =============================================================================


class InMemoryStateRepository(StateRepository):
    """In-memory state storage with auto-cleanup."""

    def __init__(self):
        self._store: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def store(self, state: str, ttl_seconds: int = 600) -> None:
        async with self._lock:
            # Clean up expired states
            now = datetime.now(timezone.utc)
            expired = [s for s, exp in self._store.items() if now > exp]
            for s in expired:
                del self._store[s]

            self._store[state] = now + timedelta(seconds=ttl_seconds)

    async def validate_and_consume(self, state: str) -> bool:
        async with self._lock:
            if state not in self._store:
                return False

            expires_at = self._store.pop(state)
            return datetime.now(timezone.utc) <= expires_at
