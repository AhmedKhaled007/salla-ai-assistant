"""Health and tools endpoints."""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from ...services import MCPClientPool, get_valid_access_token
from .auth import get_auth_session_id

router = APIRouter()

# Global pool instance (injected from main app state normally, but simplifying for now)
# We need to access the pool created in main.py. 
# A better pattern is to use request.app.state.pool or dependency injection.
# For now, we'll assume the pool is available via dependency or imported singleton.
# Since client_pool.py doesn't export a singleton but a class, we need to handle this.
# Let's use a simple dependency that gets the pool from app.state.

from fastapi import Request

def get_pool(request: Request) -> MCPClientPool:
    return request.app.state.pool


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for load balancer probes.
    
    Performs live ping to MCP server to verify connectivity.
    Returns MCP connection status, LLM availability, and pool info.
    """
    pool = get_pool(request)
    mcp_status = await pool.ping()
    
    return {
        "status": "healthy" if mcp_status else "degraded",
        "mcp_server": "connected" if mcp_status else "disconnected",
        "pool_size": pool.pool_size(),
        "active_clients": pool.active_clients(),
    }


@router.get("/tools")
async def get_tools(
    request: Request,
    auth_session_id: str = Depends(get_auth_session_id)
) -> Dict[str, Any]:
    """Get the list of available tools."""
    pool = get_pool(request)
    try:
        access_token = await get_valid_access_token(auth_session_id)
        client = await pool.get_client(auth_session_id, access_token)
        tools = await client.get_mcp_tools()
        return {"tools": [t.name for t in tools]}
    except Exception as e:
        return {"error": str(e), "tools": []}
