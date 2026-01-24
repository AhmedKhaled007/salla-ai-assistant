from typing import Dict, Any
import asyncio
from fastapi import APIRouter, Depends, Request

from agent.services import get_valid_access_token
from agent.api.dependencies import get_mcp_client, get_auth_session_id

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for load balancer probes.

    Performs live ping to MCP server to verify connectivity.
    Returns MCP connection status and LLM availability.
    """
    mcp_client = get_mcp_client(request)
    try:
        mcp_status = await asyncio.wait_for(mcp_client.ping(), timeout=5.0)
    except (Exception, asyncio.CancelledError):
        mcp_status = False

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
