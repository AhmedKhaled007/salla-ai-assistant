"""Session management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from ...services import MCPClientPool

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/sessions")
async def create_session(req: Request):
    """Create a new conversation session."""
    pool = get_pool(req)
    # We can use default client to generate a session ID since IDs are universal
    # or just use uuid here directly. But strictly speaking, session creating calls client.
    client = await pool.get_client(None, None)
    session_id = await client.create_session()
    return {"session_id": session_id}


@router.get("/sessions")
async def list_sessions(req: Request):
    """List all active session IDs."""
    pool = get_pool(req)
    client = await pool.get_client(None, None)
    sessions = await client.list_sessions()
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, req: Request):
    """Get messages for a specific session."""
    pool = get_pool(req)
    # Session storage is shared, so any client can access (in this current design)
    client = await pool.get_client(None, None)
    messages = await client.get_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, req: Request):
    """Delete a conversation session."""
    pool = get_pool(req)
    client = await pool.get_client(None, None)
    success = await client.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}
