"""Conversation management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from ...services import MCPClientPool, get_valid_access_token
from .auth import get_auth_session_id

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/conversations")
async def create_conversation(
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Create a new conversation."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    conversation_id = await client.create_conversation()
    return {"conversation_id": conversation_id}


@router.get("/conversations")
async def list_conversations(
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """List all active conversation IDs."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    conversations = await client.list_conversations()
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, 
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Get messages for a specific conversation."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    messages = await client.get_conversation(conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, 
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Delete a conversation."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    success = await client.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success"}
