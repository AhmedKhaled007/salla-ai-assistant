"""Shared utilities for the Salla MCP server."""
import logging
from typing import Any
from mcp.server.fastmcp import Context
from .salla_client import SallaClient

logger = logging.getLogger(__name__)

def format_error(error: Exception) -> dict:
    """Format error as dict."""
    return {"error": str(error)}

def get_salla_client(ctx: Context) -> SallaClient:
    """Extract access token from request context and create a per-request SallaClient.

    For HTTP transport, the token is passed in the Authorization header.
    This function extracts it and creates a new client instance for this request,
    ensuring no token leakage between concurrent requests.

    Args:
        ctx: MCP Context object containing request information

    Returns:
        SallaClient instance with the request's access token

    Raises:
        ValueError: If no authorization token is found in the request
    """
    try:
        request = ctx.request_context.request
        if request:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                return SallaClient(access_token=token)
    except Exception as e:
        # If not in HTTP context (stdio transport), fall through to error
        logger.error(f"Error extracting token from context: {e}")

    raise ValueError("No authorization token found in request. Please authenticate first.")
