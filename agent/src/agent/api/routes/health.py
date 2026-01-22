from typing import Dict, Any
from fastapi import APIRouter, Depends, Request

from ...services import MCPClient, get_valid_access_token
from ..dependencies import get_mcp_client
from .auth import get_auth_session_id

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for load balancer probes.

    Performs live ping to MCP server to verify connectivity.
    Returns MCP connection status and LLM availability.
    """
    mcp_client = get_mcp_client(request)
    mcp_status = await mcp_client.ping()

    return {
        "status": "healthy",
        "mcp_server": "connected" if mcp_status else "disconnected",
    }


@router.get("/tools")
async def get_tools(
    request: Request,
    auth_session_id: str = Depends(get_auth_session_id)
) -> Dict[str, Any]:
    """Get the list of available tools."""
    mcp_client = get_mcp_client(request)
    try:
        access_token = await get_valid_access_token(auth_session_id)
        tools = await mcp_client.get_mcp_tools(token=access_token)
        return {"tools": [t.name for t in tools]}
    except Exception as e:
        return {"error": str(e), "tools": []}
