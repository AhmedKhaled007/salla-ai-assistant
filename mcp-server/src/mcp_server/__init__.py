"""Salla MCP Server package."""
from typing import TYPE_CHECKING, Any

from .config import settings
from .salla_client import SallaClient

if TYPE_CHECKING:
    from .main import mcp


def __getattr__(name: str) -> Any:
    """Load the server lazily so ``python -m mcp_server.main`` runs once."""
    if name == "mcp":
        from .main import mcp

        return mcp
    raise AttributeError(name)


__all__ = ["mcp", "settings", "SallaClient"]
