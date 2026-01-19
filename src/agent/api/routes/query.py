"""Query processing endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..models import QueryRequest
from ...services import MCPClientPool
from fastapi import Request

router = APIRouter()

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.post("/query")
async def process_query(
    request: QueryRequest,
    req: Request,
):
    """Process a query and return the response.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    If session_id is provided, continues the existing conversation.
    If auth_session_id is provided, uses the user's OAuth token.
    """
    pool = get_pool(req)
    
    # Get access token from session if authenticated
    access_token = None
    if request.auth_session_id:
        from ...services import get_valid_access_token
        access_token = await get_valid_access_token(request.auth_session_id)
        if not access_token:
            # Token expired or invalid
            # We could proceed unauthenticated OR fail. 
            # If user sent auth_session_id, they expect auth context.
            # But maybe they just want to chat unauthenticated?
            # Let's log warning and proceed unauthenticated if getting token fails?
            # Actually, `get_valid_access_token` tries refresh. If it returns None, it means
            # we really can't authenticate.
            pass

    try:
        client = await pool.get_client(request.auth_session_id, access_token)
        messages = await client.process_query(request.query, request.session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def process_query_stream(
    request: QueryRequest,
    req: Request,
):
    """Process a query with Server-Sent Events streaming.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    Returns events as they happen: session, tool_call, tool_result, response, error, done.
    """
    pool = get_pool(req)
    
    # Get access token logic (duplicated, could be dry-ed)
    access_token = None
    if request.auth_session_id:
        from ...services import get_valid_access_token
        access_token = await get_valid_access_token(request.auth_session_id)

    try:
        client = await pool.get_client(request.auth_session_id, access_token)
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
