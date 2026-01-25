from fastapi import Request, HTTPException, Depends, Header
from agent.services.mcp_client import MCPClient
from agent.services.query_processor import QueryProcessor
from agent.services.auth_service import get_tokens


def get_mcp_client(request: Request) -> MCPClient:
    """Dependency to get the singleton MCPClient from app state."""
    return request.app.state.mcp_client


def get_query_processor(request: Request) -> QueryProcessor:
    """Dependency to get QueryProcessor."""
    # We can perform dependency injection here
    return QueryProcessor(request.app.state.mcp_client)


async def get_auth_session_id(
    x_auth_session_id: str | None = Header(default=None, alias="X-Auth-Session-Id")
) -> str:
    if not x_auth_session_id:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Session-Id header")
    return x_auth_session_id


async def get_user_id(auth_session_id: str = Depends(get_auth_session_id)) -> int:
    """Extract user_id from auth session, raising 401 if not found."""
    tokens = await get_tokens(auth_session_id)
    if not tokens or not tokens.get("user_id"):
        raise HTTPException(status_code=401, detail="User identity not found for session")
    return tokens.get("user_id")
