"""Token repository for OAuth token storage.

Contains the abstract TokenRepository interface and implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timedelta, timezone
import asyncio
from sqlalchemy import select, delete
from agent.core.database import AsyncSessionLocal
from agent.core.models import AuthSession


def _as_utc(value: datetime | str) -> datetime:
    """Normalize database and serialized datetimes to aware UTC values."""
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class TokenRepository(ABC):
    """Repository for OAuth tokens (access_token, refresh_token)."""

    @abstractmethod
    async def store(
        self, session_id: str, tokens: dict, ttl_seconds: int = 3600, user_id: int | None = None
    ) -> None:
        """Store tokens with optional TTL.

        Args:
            session_id: Unique session identifier
            tokens: Dict containing access_token, refresh_token, expires_at, merchant_info, user_id
            ttl_seconds: Time-to-live in seconds (default 1 hour)
            user_id: Optional user ID to link session to user
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


# =============================================================================
# IN-MEMORY IMPLEMENTATION
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
        self, session_id: str, tokens: dict, ttl_seconds: int = 3600, user_id: int | None = None
    ) -> None:
        async with self._lock:
            self._store[session_id] = {
                **tokens,
                "user_id": user_id,
                "_expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            }

    async def get(self, session_id: str) -> Optional[dict]:
        async with self._lock:
            data = self._store.get(session_id)
            if not data:
                return None

            # Check expiry
            if datetime.now(timezone.utc) > data.get("_expires_at", datetime.max.replace(tzinfo=timezone.utc)):
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


class SQLAlchemyTokenRepository(TokenRepository):
    """SQLAlchemy-based token storage."""

    async def store(
        self, session_id: str, tokens: dict, ttl_seconds: int = 3600, user_id: int | None = None
    ) -> None:
        async with AsyncSessionLocal() as session:
            raw_access_expiry = tokens.get("expires_at")
            if raw_access_expiry is None:
                raise ValueError("tokens.expires_at is required")

            access_expires_at = _as_utc(raw_access_expiry)
            retention_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=ttl_seconds
            )

            # Check if exists
            stmt = select(AuthSession).where(AuthSession.session_id == session_id)
            result = await session.execute(stmt)
            auth_session = result.scalar_one_or_none()

            if auth_session:
                # Update
                auth_session.access_token = tokens["access_token"]
                auth_session.refresh_token = tokens.get("refresh_token")
                auth_session.expires_at = access_expires_at
                auth_session.retention_expires_at = retention_expires_at
                auth_session.scope = tokens.get("scope")
                auth_session.merchant_info = tokens.get("merchant_info")
                if user_id is not None:
                    auth_session.user_id = user_id
            else:
                # Insert
                auth_session = AuthSession(
                    session_id=session_id,
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token"),
                    expires_at=access_expires_at,
                    retention_expires_at=retention_expires_at,
                    scope=tokens.get("scope"),
                    merchant_info=tokens.get("merchant_info"),
                    user_id=user_id
                )
                session.add(auth_session)

            await session.commit()

    async def get(self, session_id: str) -> Optional[dict]:
        async with AsyncSessionLocal() as session:
            stmt = select(AuthSession).where(AuthSession.session_id == session_id)
            result = await session.execute(stmt)
            auth_session = result.scalar_one_or_none()

            if not auth_session:
                return None

            if _as_utc(auth_session.retention_expires_at) < datetime.now(timezone.utc):
                await session.delete(auth_session)
                await session.commit()
                return None

            return {
                "access_token": auth_session.access_token,
                "refresh_token": auth_session.refresh_token,
                "expires_at": _as_utc(auth_session.expires_at).isoformat(),
                "scope": auth_session.scope,
                "merchant_info": auth_session.merchant_info,
                "user_id": auth_session.user_id,
            }

    async def delete(self, session_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            stmt = select(AuthSession).where(AuthSession.session_id == session_id)
            result = await session.execute(stmt)
            auth_session = result.scalar_one_or_none()

            if auth_session:
                await session.delete(auth_session)
                await session.commit()
                return True
            return False

    async def exists(self, session_id: str) -> bool:
        return await self.get(session_id) is not None
