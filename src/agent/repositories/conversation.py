"""Conversation repository for chat session storage.

Contains the abstract ConversationRepository interface and implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio
import json
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from ..core.database import get_db
from ..core.models import Conversation, Message


class ConversationRepository(ABC):
    """Repository for conversation sessions (optional persistence)."""

    @abstractmethod
    async def store(self, conversation_id: str, messages: list) -> None:
        """Store conversation messages."""

    @abstractmethod
    async def get(self, conversation_id: str) -> Optional[list]:
        """Get messages for conversation."""

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool:
        """Delete conversation. Returns True if existed."""

    @abstractmethod
    async def list_conversations(self) -> list[str]:
        """List all conversation IDs."""


# =============================================================================
# IN-MEMORY IMPLEMENTATION
# =============================================================================


class InMemoryConversationRepository(ConversationRepository):
    """In-memory conversation storage."""

    def __init__(self):
        self._store: dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def store(self, conversation_id: str, messages: list) -> None:
        async with self._lock:
            self._store[conversation_id] = messages

    async def get(self, conversation_id: str) -> Optional[list]:
        async with self._lock:
            return self._store.get(conversation_id)

    async def delete(self, conversation_id: str) -> bool:
        async with self._lock:
            if conversation_id in self._store:
                del self._store[conversation_id]
                return True
            return False

    async def list_conversations(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())


class SQLAlchemyConversationRepository(ConversationRepository):
    """SQLAlchemy-based conversation storage."""

    async def store(self, conversation_id: str, messages: list) -> None:
        async for session in get_db():
            # Check if conversation exists
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                conversation = Conversation(id=conversation_id)
                session.add(conversation)
                await session.flush() # ensure ID is available
            
            # Delete existing messages to replace them (inefficient but simple for now)
            # A better approach would be to differential update, but messages don't have IDs in the input list.
            await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
            
            # Insert new messages
            for msg in messages:
                # msg is a dict with 'role', 'content', and potentially 'tool_calls', etc.
                role = msg.get("role")
                content = msg.get("content")
                
                # Check for tool result messages (need to preserve tool_call_id/name)
                # or assistant messages with tool_calls (content is None/empty)
                if role == "tool" or not content:
                    # Serialize the entire message to preserve keys
                    content = json.dumps(msg, ensure_ascii=False)
                elif not isinstance(content, str):
                    # If content is a complex object, serialize it
                    content = json.dumps(content, ensure_ascii=False)
                    
                message = Message(
                    conversation_id=conversation_id,
                    role=msg.get("role"),
                    content=content
                    # created_at automatically handled
                )
                session.add(message)
            
            await session.commit()

    async def get(self, conversation_id: str) -> Optional[list]:
        async for session in get_db():
            stmt = select(Conversation).options(
                selectinload(Conversation.messages)
            ).where(Conversation.id == conversation_id)
            
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return None
                
            # Convert to list of dicts, sorted by created_at
            messages = []
            sorted_messages = sorted(conversation.messages, key=lambda m: m.created_at)
            
            for msg in sorted_messages:
                content = msg.content
                # Try to parse JSON content (for tool call messages that were serialized)
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "role" in parsed:
                        # This was a serialized message (e.g., tool call), use it directly
                        messages.append(parsed)
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                    
                messages.append({
                    "role": msg.role,
                    "content": content
                })
            
            return messages

    async def delete(self, conversation_id: str) -> bool:
        async for session in get_db():
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                await session.delete(conversation)
                await session.commit()
                return True
            return False

    async def list_conversations(self) -> list[str]:
        async for session in get_db():
            stmt = select(Conversation.id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
