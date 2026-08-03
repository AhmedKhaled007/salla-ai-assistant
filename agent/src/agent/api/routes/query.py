"""Query processing endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi import Request
import json


from agent.api.models import QueryRequest
from agent.services import get_valid_access_token
from agent.api.dependencies import get_query_processor, get_user_id, get_auth_session_id

router = APIRouter()


@router.post("/query")
async def process_query(
    request: QueryRequest,
    req: Request,
    auth_session_id: str | None = Depends(get_auth_session_id)
):
    """Process a query and return the response.

    Uses QueryProcessor service to process queries with token isolation.
    Creates a conversation when conversation_id is omitted; otherwise continues it.
    If auth_session_id is provided (via header), uses the user's OAuth token.
    """
    query_processor = get_query_processor(req)

    # Get access token from session if authenticated
    access_token = None
    if auth_session_id:
        access_token = await get_valid_access_token(auth_session_id)

    try:
        conversation_id, messages = await query_processor.process_query(
            request.query,
            request.conversation_id,
            token=access_token,
            user_id=await get_user_id(auth_session_id) if auth_session_id else None
        )
        return {"conversation_id": conversation_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def process_query_stream(
    request: QueryRequest,
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Process a query with Server-Sent Events streaming.

    Uses QueryProcessor service to process queries with token isolation.
    Returns events as they happen: conversation, tool_call, tool_result, response, error, done.
    """
    query_processor = get_query_processor(req)
    access_token = await get_valid_access_token(auth_session_id)

    async def event_generator():

        try:
            # We already have access_token, but let's also get user_id
            user_id = await get_user_id(auth_session_id)
            async for event in query_processor.process_query_stream(
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
