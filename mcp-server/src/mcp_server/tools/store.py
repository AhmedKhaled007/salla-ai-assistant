"""Store tools for Salla MCP Server."""
from mcp.server.mcpserver import Context

from ..utils import get_salla_client, format_error

__all__ = ["salla_get_store_info"]


async def salla_get_store_info(ctx: Context) -> dict:
    """
    Get information about the Salla store.

    Returns:
        dict: Store details including name, domain, plan, currency, settings
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get("/store/info")
        return result
    except Exception as e:
        return format_error(e)
