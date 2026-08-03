"""Tests for the demo MCP v2 wrapper."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from agent.services.mcp_client import MCPClient


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None


class _ConnectedClient(_AsyncContext):
    protocol_version = "2026-07-28"
    server_info = None


@pytest.mark.asyncio
async def test_http_connection_passes_the_user_token():
    captured = {}

    def make_http_client(**kwargs):
        captured.update(kwargs)
        return _AsyncContext()

    with (
        patch("agent.services.mcp_client.httpx2.AsyncClient", side_effect=make_http_client),
        patch("agent.services.mcp_client.streamable_http_client", return_value=object()),
        patch("agent.services.mcp_client.Client", return_value=_ConnectedClient()),
    ):
        async with MCPClient(server_url="https://mcp.example/mcp").connect("merchant-token"):
            pass

    assert captured["headers"] == {"Authorization": "Bearer merchant-token"}


@pytest.mark.asyncio
async def test_get_openai_tools_uses_v2_schema_attributes():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}},
    }
    sdk_client = AsyncMock()
    sdk_client.list_tools.return_value = ListToolsResult(tools=[
        Tool(name="lookup", description="Look up an item", inputSchema=schema),
    ])

    tools = await MCPClient().get_openai_tools(sdk_client)

    assert tools == [{
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look up an item",
            "parameters": schema,
        },
    }]


@pytest.mark.asyncio
async def test_execute_tool_returns_structured_json_or_text():
    sdk_client = AsyncMock()
    sdk_client.call_tool.side_effect = [
        CallToolResult(
            content=[TextContent(type="text", text='{"ok":true}')],
            structuredContent={"ok": True},
        ),
        CallToolResult(content=[TextContent(type="text", text="plain text")]),
    ]
    client = MCPClient()

    structured = await client.execute_tool(sdk_client, "lookup", {"id": 1})
    text = await client.execute_tool(sdk_client, "lookup", {"id": 2})

    assert json.loads(structured) == {"ok": True}
    assert text == "plain text"
