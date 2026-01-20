import uuid
from typing import Optional
from ..core import get_conversation_repository, logger
from .llm import call_llm

class ConversationService:
    """Service for managing conversation lifecycle and history."""
    
    def __init__(self):
        self._conversation_repo = get_conversation_repository()

    async def create_conversation(self, user_id: int, title: str = "New Conversation") -> str:
        """Create a new conversation session and return its ID."""
        conversation_id = str(uuid.uuid4())
        await self._conversation_repo.create(conversation_id, user_id, title)
        logger.info(f"Created new conversation: {conversation_id} with title: {title}")
        return conversation_id

    async def get_history(self, conversation_id: str) -> list:
        """Get messages for a conversation. Returns empty list if not found."""
        messages = await self._conversation_repo.get(conversation_id)
        return messages if messages else []

    async def save_history(self, conversation_id: str, messages: list) -> None:
        """Save conversation history."""
        await self._conversation_repo.store(conversation_id, messages)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation. Returns True if conversation existed."""
        return await self._conversation_repo.delete(conversation_id)

    async def list_conversations(self) -> list[dict]:
        """List all active conversations."""
        return await self._conversation_repo.list_conversations()

    async def update_title(self, conversation_id: str, title: str) -> None:
        """Update the title of a conversation."""
        await self._conversation_repo.update_title(conversation_id, title)

    async def generate_title(self, query: str) -> str:
        """Generate a short title for the conversation based on the query."""
        system_prompt = (
            "You are a helpful assistant. Generate a short, concise title (3-5 words) "
            "for a conversation based on the following user query. "
            "Do not use quotes or markdown, just the plain text title."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        try:
            response = await call_llm(messages)
            title = response.choices[0].message.content.strip()
            # Clean up any potential quotes
            title = title.strip('"\'')
            return title
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            return "New Conversation"
