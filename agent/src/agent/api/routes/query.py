"""Query processing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi import Request

from ..models import QueryRequest
from ...services import MCPClient, get_valid_access_token
from ..dependencies import get_mcp_client, get_user_id
from .auth import get_auth_session_id

router = APIRouter()


@router.post("/query")
async def process_query(
    request: QueryRequest,
    req: Request,
    auth_session_id: str | None = Depends(get_auth_session_id)
):
    """Process a query and return the response.

    Uses MCPClient singleton to process queries with token isolation.
    If conversation_id is provided, continues the existing conversation.
    If auth_session_id is provided (via header), uses the user's OAuth token.
    """
    mcp_client = get_mcp_client(req)

    # Get access token from session if authenticated
    access_token = None
    if auth_session_id:
        access_token = await get_valid_access_token(auth_session_id)

    try:
        messages = await mcp_client.process_query(
            request.query,
            request.conversation_id,
            token=access_token,
            user_id=await get_user_id(auth_session_id) if auth_session_id else None
        )
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

    Uses MCPClient singleton to process queries with token isolation.
    Returns events as they happen: conversation, tool_call, tool_result, response, error, done.
    """
    mcp_client = get_mcp_client(req)
    access_token = await get_valid_access_token(auth_session_id)

    async def event_generator():
        import json
        try:
            # We already have access_token, but let's also get user_id
            user_id = await get_user_id(auth_session_id)
            async for event in mcp_client.process_query_stream(
                request.query,
                request.conversation_id,
                token=access_token,
                user_id=user_id
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
