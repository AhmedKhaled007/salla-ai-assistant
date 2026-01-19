"""Query processing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi import Request

from ..models import QueryRequest
from ...services import MCPClientPool, get_valid_access_token
from .auth import get_auth_session_id

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/query")
async def process_query(
    request: QueryRequest,
    req: Request,
    auth_session_id: str | None = Depends(get_auth_session_id)
):
    """Process a query and return the response.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    If session_id is provided, continues the existing conversation.
    If auth_session_id is provided (via header), uses the user's OAuth token.
    """
    pool = get_pool(req)
    
    # Get access token from session if authenticated
    access_token = None
    if auth_session_id:
        access_token = await get_valid_access_token(auth_session_id)
        # Note: If token is None, we proceed as unauthenticated/guest if allowed,
        # or the pool/client might enforce auth. For now, we pass what we have.

    try:
        client = await pool.get_client(auth_session_id, access_token)
        messages = await client.process_query(request.query, request.session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def process_query_stream(
    request: QueryRequest,
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Process a query with Server-Sent Events streaming.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    Returns events as they happen: session, tool_call, tool_result, response, error, done.
    """
    pool = get_pool(req)
    
    access_token = await get_valid_access_token(auth_session_id)

    try:
        client = await pool.get_client(auth_session_id, access_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client: {e}")

    async def event_generator():
        import json
        try:
            async for event in client.process_query_stream(request.query, request.session_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
 