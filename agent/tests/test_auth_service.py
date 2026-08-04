"""Regression tests for OAuth access-token expiry handling."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent.core.database import Base
from agent.repositories import token as token_repository_module
from agent.repositories.token import SQLAlchemyTokenRepository
from agent.services import auth_service


@pytest.mark.asyncio
async def test_expired_access_token_remains_available_for_refresh(
    monkeypatch,
):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(
        token_repository_module,
        "AsyncSessionLocal",
        session_factory,
    )
    repository = SQLAlchemyTokenRepository()
    monkeypatch.setattr(auth_service, "_token_repo", repository)

    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await repository.store(
        "session-id",
        {
            "access_token": "expired-access-token",
            "refresh_token": "refresh-token",
            "expires_at": expired_at.isoformat(),
            "merchant_info": {"id": 1},
        },
        ttl_seconds=86400,
        user_id=42,
    )

    stored_before_refresh = await repository.get("session-id")
    assert stored_before_refresh is not None
    assert datetime.fromisoformat(stored_before_refresh["expires_at"]) <= datetime.now(
        timezone.utc
    )

    refresh = AsyncMock(return_value={
        "access_token": "new-access-token",
        "expires_in": 3600,
    })
    monkeypatch.setattr(auth_service, "refresh_access_token", refresh)

    access_token = await auth_service.get_valid_access_token("session-id")

    assert access_token == "new-access-token"
    refresh.assert_awaited_once_with("refresh-token")
    stored_after_refresh = await repository.get("session-id")
    assert stored_after_refresh is not None
    assert stored_after_refresh["refresh_token"] == "refresh-token"
    assert stored_after_refresh["user_id"] == 42

    await engine.dispose()
