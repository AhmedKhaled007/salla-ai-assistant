"""Small MCP SDK v2 wrapper used by the demo agent."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from typing import Any, AsyncIterator

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from agent.core import logger, settings


class MCPClient:
    """Create token-scoped MCP v2 clients for a query or health check."""

    def __init__(self, server_url: str | None = None) -> None:
        self.server_url = server_url or settings.mcp_server_url

    @asynccontextmanager
    async def connect(self, token: str | None = None) -> AsyncIterator[Client]:
        """Open a client and close it when the current operation finishes."""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx2.AsyncClient(
            headers=headers,
            timeout=httpx2.Timeout(30.0, read=300.0),
            follow_redirects=True,
        ) as http_client:
            transport = streamable_http_client(
                self.server_url,
                http_client=http_client,
            )
            async with Client(
                transport,
                mode="auto",
                read_timeout_seconds=settings.tool_timeout,
            ) as client:
                yield client

    async def get_openai_tools(self, client: Client) -> list[dict[str, Any]]:
        """List tools once and convert them to the LLM function format."""
        result = await client.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or tool.title or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in result.tools
        ]

    async def execute_tool(
        self,
        client: Client,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        """Call one MCP tool and return a string suitable for an LLM message."""
        result = await client.call_tool(
            tool_name,
            tool_args,
            read_timeout_seconds=settings.tool_timeout,
        )
        logger.info("MCP tool %s completed (is_error=%s)", tool_name, result.is_error)

        if result.structured_content is not None:
            return json.dumps(result.structured_content, ensure_ascii=False)

        text = [block.text for block in result.content if isinstance(block, TextContent)]
        if text:
            return "\n".join(text)
        return result.model_dump_json(by_alias=True, exclude_none=True)

    async def probe(self) -> dict[str, Any]:
        """Check MCP availability using tools/list; modern MCP has no ping."""
        try:
            async with asyncio.timeout(5.0):
                async with self.connect() as client:
                    tools = await client.list_tools()
                    server_name = client.server_info.name if client.server_info else None
                    return {
                        "connected": True,
                        "protocol_version": client.protocol_version,
                        "server_name": server_name,
                        "tool_count": len(tools.tools),
                    }
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("MCP probe failed: %s", type(error).__name__)
            return {
                "connected": False,
                "protocol_version": None,
                "server_name": None,
                "tool_count": None,
            }
