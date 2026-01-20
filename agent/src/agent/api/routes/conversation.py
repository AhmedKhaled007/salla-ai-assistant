"""Conversation management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from ...services import ConversationService, get_tokens
from .auth import get_auth_session_id

router = APIRouter()




@router.post("/conversations")
async def create_conversation(
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Create a new conversation."""
    tokens = await get_tokens(auth_session_id)
    if not tokens or not tokens.get("user_id"):
        raise HTTPException(status_code=401, detail="User Identity not found for session")
    
    user_id = tokens.get("user_id")
    service = ConversationService()
    conversation_id = await service.create_conversation(user_id=user_id)
    return {"conversation_id": conversation_id}


@router.get("/conversations")
async def list_conversations(
    auth_session_id: str = Depends(get_auth_session_id)
):
    """List all active conversation IDs."""
    service = ConversationService()
    conversations = await service.list_conversations()
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, 
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Get messages for a specific conversation."""
    service = ConversationService()
    messages = await service.get_history(conversation_id)
    # Service returns [] if not found or empty, which is acceptable for now.
    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, 
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Delete a conversation."""
    service = ConversationService()
    success = await service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success"}
