"""Abstract repository pattern for flexible storage backends.

This module provides abstract base classes and in-memory implementations
for all storage needs. To switch to Redis/PostgreSQL, implement the
abstract classes and update dependencies.py.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timedelta
import asyncio


# =============================================================================
# ABSTRACT BASE CLASSES
# =============================================================================


class TokenRepository(ABC):
    """Repository for OAuth tokens (access_token, refresh_token)."""

    @abstractmethod
    async def store(
        self, session_id: str, tokens: dict, ttl_seconds: int = 3600
    ) -> None:
        """Store tokens with optional TTL.
        
        Args:
            session_id: Unique session identifier
            tokens: Dict containing access_token, refresh_token, expires_at, merchant_info
            ttl_seconds: Time-to-live in seconds (default 1 hour)
        """

    @abstractmethod
    async def get(self, session_id: str) -> Optional[dict]:
        """Get tokens by session ID.
        
        Returns:
            Token dict or None if not found/expired
        """

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete tokens.
        
        Returns:
            True if existed and was deleted
        """

    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """Check if session has valid tokens."""


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


class ConversationRepository(ABC):
    """Repository for conversation sessions (optional persistence)."""

    @abstractmethod
    async def store(self, session_id: str, messages: list) -> None:
        """Store conversation messages."""

    @abstractmethod
    async def get(self, session_id: str) -> Optional[list]:
        """Get messages for session."""

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete session. Returns True if existed."""

    @abstractmethod
    async def list_sessions(self) -> list[str]:
        """List all session IDs."""


# =============================================================================
# IN-MEMORY IMPLEMENTATIONS
# =============================================================================


class InMemoryTokenRepository(TokenRepository):
    """In-memory token storage with expiry tracking.
    
    Suitable for development/single-instance deployments.
    For production with multiple instances, use RedisTokenRepository.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def store(
        self, session_id: str, tokens: dict, ttl_seconds: int = 3600
    ) -> None:
        async with self._lock:
            self._store[session_id] = {
                **tokens,
                "_expires_at": datetime.now() + timedelta(seconds=ttl_seconds),
            }

    async def get(self, session_id: str) -> Optional[dict]:
        async with self._lock:
            data = self._store.get(session_id)
            if not data:
                return None
            
            # Check expiry
            if datetime.now() > data.get("_expires_at", datetime.max):
                del self._store[session_id]
                return None
            
            # Return without internal fields
            return {k: v for k, v in data.items() if not k.startswith("_")}

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    async def exists(self, session_id: str) -> bool:
        return await self.get(session_id) is not None


class InMemoryStateRepository(StateRepository):
    """In-memory state storage with auto-cleanup."""

    def __init__(self):
        self._store: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def store(self, state: str, ttl_seconds: int = 600) -> None:
        async with self._lock:
            # Clean up expired states
            now = datetime.now()
            expired = [s for s, exp in self._store.items() if now > exp]
            for s in expired:
                del self._store[s]
            
            self._store[state] = now + timedelta(seconds=ttl_seconds)

    async def validate_and_consume(self, state: str) -> bool:
        async with self._lock:
            if state not in self._store:
                return False
            
            expires_at = self._store.pop(state)
            return datetime.now() <= expires_at


class InMemoryRateLimitRepository(RateLimitRepository):
    """In-memory rate limiter using sliding window."""

    def __init__(self):
        self._store: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check_and_increment(
        self, key: str, limit: int, window_seconds: int
    ) -> bool:
        import time
        
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            
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
        import time
        
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            
            timestamps = self._store.get(key, [])
            current_count = len([t for t in timestamps if t > window_start])
            return max(0, limit - current_count)


class InMemoryConversationRepository(ConversationRepository):
    """In-memory conversation storage."""

    def __init__(self):
        self._store: dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def store(self, session_id: str, messages: list) -> None:
        async with self._lock:
            self._store[session_id] = messages

    async def get(self, session_id: str) -> Optional[list]:
        async with self._lock:
            return self._store.get(session_id)

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    async def list_sessions(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())
