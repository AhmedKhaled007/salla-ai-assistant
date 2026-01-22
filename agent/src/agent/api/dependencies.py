from fastapi import Request, HTTPException, Depends
from ..services.mcp_client import MCPClient
from ..services.auth_service import get_tokens
from .routes.auth import get_auth_session_id


def get_mcp_client(request: Request) -> MCPClient:
    """Dependency to get the singleton MCPClient from app state."""
    return request.app.state.mcp_client


async def get_user_id(auth_session_id: str = Depends(get_auth_session_id)) -> int:
    """Extract user_id from auth session, raising 401 if not found."""
    tokens = await get_tokens(auth_session_id)
    if not tokens or not tokens.get("user_id"):
        raise HTTPException(status_code=401, detail="User identity not found for session")
    return tokens.get("user_id")
