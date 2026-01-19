"""Services layer for business logic.

This package contains the core business logic of the application,
including the MCP client, authentication service, and LLM interactions.
"""

from .mcp_client import MCPClient
from .client_pool import MCPClientPool
from .conversation import ConversationService
from .auth_service import (
    generate_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_merchant_info,
    store_tokens,
    get_tokens,
    delete_tokens,
    is_authenticated,
    get_valid_access_token,
    store_state,
    validate_state,
    generate_state,
)
from .prompts import SYSTEM_PROMPT

__all__ = [
    "MCPClient",
    "MCPClientPool",
    "ConversationService",
    "generate_auth_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "get_merchant_info",
    "store_tokens",
    "get_tokens",
    "delete_tokens",
    "is_authenticated",
    "get_valid_access_token",
    "store_state",
    "validate_state",
    "generate_state",
    "SYSTEM_PROMPT",
]
