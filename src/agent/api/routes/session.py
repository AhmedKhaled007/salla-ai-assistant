"""Session management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from ...services import MCPClientPool, get_valid_access_token
from .auth import get_auth_session_id

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/sessions")
async def create_session(
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Create a new conversation session."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    session_id = await client.create_session()
    return {"session_id": session_id}


@router.get("/sessions")
async def list_sessions(
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """List all active session IDs."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    sessions = await client.list_sessions()
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str, 
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Get messages for a specific session."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    messages = await client.get_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, 
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Delete a conversation session."""
    pool = get_pool(req)
    access_token = await get_valid_access_token(auth_session_id)
    client = await pool.get_client(auth_session_id, access_token)
    success = await client.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}
