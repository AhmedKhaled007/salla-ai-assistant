"""Query processing endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi import Request
import json


from agent.api.models import QueryRequest
from agent.services import get_valid_access_token
from agent.services.conversation import exclude_system_messages
from agent.api.dependencies import get_query_processor, get_user_id, get_auth_session_id

router = APIRouter()


@router.post("/query")
async def process_query(
    request: QueryRequest,
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Process a query and return the response.

    Uses QueryProcessor service to process queries with token isolation.
    Creates a conversation when conversation_id is omitted; otherwise continues it.
    Uses the authenticated user's OAuth token.
    """
    query_processor = get_query_processor(req)

    access_token = await get_valid_access_token(auth_session_id)
    user_id = await get_user_id(auth_session_id)

    try:
        conversation_id, messages = await query_processor.process_query(
            request.query,
            request.conversation_id,
            token=access_token,
            user_id=user_id,
        )
        return {
            "conversation_id": conversation_id,
            "messages": exclude_system_messages(messages),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/query/stream")
async def process_query_stream(
    request: QueryRequest,
    req: Request,
    auth_session_id: str = Depends(get_auth_session_id)
):
    """Process a query with Server-Sent Events streaming.

    Uses QueryProcessor service to process queries with token isolation.
    Returns conversation, title, response chunks, tool activity, response, error,
    and done events.
    """
    query_processor = get_query_processor(req)
    access_token = await get_valid_access_token(auth_session_id)

    async def event_generator():
        try:
            user_id = await get_user_id(auth_session_id)
            async for event in query_processor.process_query_stream(
                request.query,
                request.conversation_id,
                token=access_token,
                user_id=user_id
            ):
                if "messages" in event:
                    event = {
                        **event,
                        "messages": exclude_system_messages(event["messages"]),
                    }
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
