"""User repository for managing user records."""

from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy import select
from ..core.database import get_db
from ..core.models import User

class UserRepository(ABC):
    """Abstract repository for user operations."""
    
    @abstractmethod
    async def get_by_salla_id(self, salla_user_id: str) -> Optional[User]:
        """Get user by Salla ID."""

    @abstractmethod
    async def create_or_update(self, salla_user_id: str, data: dict) -> User:
        """Create or update a user record."""
        
    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""


class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of user repository."""
    
    async def get_by_salla_id(self, salla_user_id: str) -> Optional[User]:
        async for session in get_db():
            stmt = select(User).where(User.salla_user_id == salla_user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        async for session in get_db():
            return await session.get(User, user_id)

    async def create_or_update(self, salla_user_id: str, data: dict) -> User:
        async for session in get_db():
            # Check if user exists
            stmt = select(User).where(User.salla_user_id == salla_user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Update fields
                for key, value in data.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
            else:
                # Create new user
                user = User(salla_user_id=salla_user_id, **data)
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            return user
