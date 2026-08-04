from agent.services import ConversationService
from agent.services.conversation import exclude_system_messages
from agent.api.dependencies import get_user_id
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter()


@router.post("/conversations")
async def create_conversation(user_id: int = Depends(get_user_id)):
    """Create a new conversation."""
    service = ConversationService()
    conversation_id = await service.create_conversation(user_id=user_id)
    return {"conversation_id": conversation_id}


@router.get("/conversations")
async def list_conversations(user_id: int = Depends(get_user_id)):
    """List all conversations for the authenticated user."""
    service = ConversationService()
    conversations = await service.list_conversations_for_user(user_id)
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: int = Depends(get_user_id)
):
    """Get messages for a specific conversation."""
    service = ConversationService()

    # Verify ownership before returning data
    if not await service.verify_ownership(conversation_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await service.get_history(conversation_id)
    return {"messages": exclude_system_messages(messages)}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: int = Depends(get_user_id)
):
    """Delete a conversation."""
    service = ConversationService()

    # Verify ownership before deleting
    if not await service.verify_ownership(conversation_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    success = await service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success"}
