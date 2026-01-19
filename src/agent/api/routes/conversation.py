"""Conversation management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from ...services import MCPClientPool

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/conversations")
async def create_conversation(req: Request):
    """Create a new conversation."""
    pool = get_pool(req)
    # We can use default client to generate a conversation ID since IDs are universal
    # or just use uuid here directly. But strictly speaking, conversation creating calls client.
    client = await pool.get_client(None, None)
    conversation_id = await client.create_conversation()
    return {"conversation_id": conversation_id}


@router.get("/conversations")
async def list_conversations(req: Request):
    """List all active conversation IDs."""
    pool = get_pool(req)
    client = await pool.get_client(None, None)
    conversations = await client.list_conversations()
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, req: Request):
    """Get messages for a specific conversation."""
    pool = get_pool(req)
    # Conversation storage is shared, so any client can access (in this current design)
    client = await pool.get_client(None, None)
    messages = await client.get_conversation(conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, req: Request):
    """Delete a conversation."""
    pool = get_pool(req)
    client = await pool.get_client(None, None)
    success = await client.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success"}
