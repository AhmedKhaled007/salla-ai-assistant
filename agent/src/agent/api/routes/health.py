from typing import Dict, Any
from fastapi import APIRouter, Depends, Request

from agent.services import get_valid_access_token
from agent.api.dependencies import get_mcp_client, get_auth_session_id

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for load balancer probes.

    Performs a live tools/list probe to verify connectivity.
    Returns MCP connection status and LLM availability.
    """
    mcp_client = get_mcp_client(request)
    probe = await mcp_client.probe()

    return {
        "status": "healthy",
        "mcp_server": "connected" if probe["connected"] else "disconnected",
        "mcp_protocol_version": probe["protocol_version"],
        "mcp_server_name": probe["server_name"],
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
        async with mcp_client.connect(access_token) as client:
            result = await client.list_tools()
            return {"tools": [tool.name for tool in result.tools]}
    except Exception as e:
        return {"error": str(e), "tools": []}
