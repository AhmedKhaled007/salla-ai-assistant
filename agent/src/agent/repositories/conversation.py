"""Conversation repository implementation."""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio
import json
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from agent.core.database import AsyncSessionLocal
from agent.core.models import Conversation, Message


SERIALIZED_MESSAGE_PREFIX = "__salla_agent_message_v1__:"


def _serialize_message(message: dict) -> str:
    """Encode a complete message without conflating it with plain content."""
    return SERIALIZED_MESSAGE_PREFIX + json.dumps(message, ensure_ascii=False)


def _deserialize_message(message: Message) -> dict:
    """Decode explicitly serialized messages and preserve all other content."""
    content = message.content

    if content.startswith(SERIALIZED_MESSAGE_PREFIX):
        try:
            parsed = json.loads(content.removeprefix(SERIALIZED_MESSAGE_PREFIX))
            if isinstance(parsed, dict) and parsed.get("role") == message.role:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return {"role": message.role, "content": content}


class ConversationRepository(ABC):
    """Abstract base class for conversation storage."""

    @abstractmethod
    async def store(self, conversation_id: str, messages: list) -> None:
        """Store conversation history."""

    @abstractmethod
    async def add_message(self, conversation_id: str, message: dict) -> None:
        """Add a single message to conversation."""

    @abstractmethod
    async def get(self, conversation_id: str) -> Optional[list]:
        """Get conversation history."""

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool:
        """Delete a conversation."""

    @abstractmethod
    async def list_conversations(self) -> list[dict]:
        """List all conversations."""

    @abstractmethod
    async def update_title(self, conversation_id: str, title: str) -> None:
        """Update conversation title."""

    @abstractmethod
    async def verify_owner(self, conversation_id: str, user_id: int) -> bool:
        """Verify conversation belongs to user."""

    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[dict]:
        """List conversations for a specific user."""


# =============================================================================
# IN-MEMORY IMPLEMENTATION
# =============================================================================


class InMemoryConversationRepository(ConversationRepository):
    """In-memory storage for testing/dev."""

    def __init__(self):
        self._store = {}
        self._lock = asyncio.Lock()

    async def store(self, conversation_id: str, messages: list) -> None:
        async with self._lock:
            self._store[conversation_id] = messages

    async def add_message(self, conversation_id: str, message: dict) -> None:
        async with self._lock:
            if conversation_id in self._store:
                self._store[conversation_id].append(message)
            else:
                self._store[conversation_id] = [message]

    async def get(self, conversation_id: str) -> Optional[list]:
        async with self._lock:
            return self._store.get(conversation_id)

    async def delete(self, conversation_id: str) -> bool:
        async with self._lock:
            if conversation_id in self._store:
                del self._store[conversation_id]
                return True
            return False

    async def list_conversations(self) -> list[dict]:
        async with self._lock:
            # In-memory just returns IDs for now as we don't store titles
            return [{"id": id, "title": None} for id in self._store.keys()]

    async def update_title(self, conversation_id: str, title: str) -> None:
        # In-memory doesn't store titles currently, but we can ignore or add a metadata store
        pass

    async def verify_owner(self, conversation_id: str, user_id: int) -> bool:
        # In-memory doesn't track ownership, always return True for dev
        return True

    async def list_for_user(self, user_id: int) -> list[dict]:
        # In-memory doesn't track user ownership
        async with self._lock:
            return [{"id": id, "title": None} for id in self._store.keys()]


class SQLAlchemyConversationRepository(ConversationRepository):
    """SQLAlchemy-based conversation storage."""

    async def store(self, conversation_id: str, messages: list) -> None:
        async with AsyncSessionLocal() as session:
            # Check if conversation exists
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                conversation = Conversation(id=conversation_id)
                session.add(conversation)
                await session.flush()  # ensure ID is available

            # 1. Get existing message count
            stmt = select(func.count()).where(Message.conversation_id == conversation_id)
            result = await session.execute(stmt)
            existing_count = result.scalar() or 0

            # 2. Strict Append: Only add messages that are new
            # We assume history is immutable and strictly additive per user requirement.
            messages_to_add = []
            if len(messages) > existing_count:
                messages_to_add = messages[existing_count:]

            # Insert new messages
            for msg in messages_to_add:
                message = Message(
                    conversation_id=conversation_id,
                    role=msg.get("role"),
                    content=_serialize_message(msg),
                )
                session.add(message)

            await session.commit()

    async def add_message(self, conversation_id: str, message: dict) -> None:
        async with AsyncSessionLocal() as session:
            role = message.get("role")

            msg_obj = Message(
                conversation_id=conversation_id,
                role=role,
                content=_serialize_message(message),
            )
            session.add(msg_obj)
            await session.commit()

    async def create(self, conversation_id: str, user_id: int, title: Optional[str] = None) -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                conversation = Conversation(id=conversation_id, user_id=user_id, title=title)
                session.add(conversation)
                await session.commit()

    async def get(self, conversation_id: str) -> Optional[list]:
        async with AsyncSessionLocal() as session:
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
                messages.append(_deserialize_message(msg))

            return messages

    async def delete(self, conversation_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                await session.delete(conversation)
                await session.commit()
                return True
            return False

    async def list_conversations(self) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).order_by(Conversation.updated_at.desc())
            result = await session.execute(stmt)
            conversations = result.scalars().all()
            return [{"id": c.id, "title": c.title} for c in conversations]

    async def update_title(self, conversation_id: str, title: str) -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                conversation.title = title
                await session.commit()

    async def verify_owner(self, conversation_id: str, user_id: int) -> bool:
        """Verify that the conversation belongs to the specified user."""
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def list_for_user(self, user_id: int) -> list[dict]:
        """List conversations for a specific user."""
        async with AsyncSessionLocal() as session:
            stmt = select(Conversation).where(
                Conversation.user_id == user_id
            ).order_by(Conversation.updated_at.desc())
            result = await session.execute(stmt)
            conversations = result.scalars().all()
            return [{"id": c.id, "title": c.title} for c in conversations]
