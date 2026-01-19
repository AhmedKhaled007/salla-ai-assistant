from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from .config import settings

# Construct database URL
# Use sqlite+aiosqlite by default if not specified
# Ensure absolute path for SQLite to avoid CWD issues
if hasattr(settings, "database_url") and settings.database_url:
    DATABASE_URL = settings.database_url
else:
    # src/agent/core/database.py -> ... -> project_root
    # .parent = core
    # .parent.parent = agent
    # .parent.parent.parent = src
    # .parent.parent.parent.parent = salla-agent (root)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    db_path = project_root / "salla_agent.db"
    DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

class Base(DeclarativeBase):
    pass

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
