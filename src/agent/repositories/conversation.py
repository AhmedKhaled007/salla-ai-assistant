"""Conversation repository for chat session storage.

Contains the abstract ConversationRepository interface and implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from ..core.database import get_db
from ..core.models import Conversation, Message


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
# IN-MEMORY IMPLEMENTATION
# =============================================================================


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


class SQLAlchemyConversationRepository(ConversationRepository):
    """SQLAlchemy-based conversation storage."""

    async def store(self, session_id: str, messages: list) -> None:
        async for session in get_db():
            # Check if conversation exists
            stmt = select(Conversation).where(Conversation.id == session_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                conversation = Conversation(id=session_id)
                session.add(conversation)
                await session.flush() # ensure ID is available
            
            # Delete existing messages to replace them (inefficient but simple for now)
            # A better approach would be to differential update, but messages don't have IDs in the input list.
            await session.execute(delete(Message).where(Message.conversation_id == session_id))
            
            # Insert new messages
            for msg in messages:
                # msg is a dict with 'role', 'content'
                message = Message(
                    conversation_id=session_id,
                    role=msg.get("role"),
                    content=msg.get("content")
                    # created_at automatically handled
                )
                session.add(message)
            
            await session.commit()

    async def get(self, session_id: str) -> Optional[list]:
        async for session in get_db():
            stmt = select(Conversation).options(
                selectinload(Conversation.messages)
            ).where(Conversation.id == session_id)
            
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return None
                
            # Convert to list of dicts, sorted by created_at (implicitly by ID/insertion order usually)
            # We should ensure order. Database usually returns in insertion order for ID, but explicit sort is better.
            # But here we rely on relationship order.
            
            messages = []
            sorted_messages = sorted(conversation.messages, key=lambda m: m.created_at)
            
            for msg in sorted_messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            return messages

    async def delete(self, session_id: str) -> bool:
        async for session in get_db():
            stmt = select(Conversation).where(Conversation.id == session_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                await session.delete(conversation)
                await session.commit()
                return True
            return False

    async def list_sessions(self) -> list[str]:
        async for session in get_db():
            stmt = select(Conversation.id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
