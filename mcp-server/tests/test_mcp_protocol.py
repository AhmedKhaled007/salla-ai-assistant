"""Protocol-level coverage for the MCP Python SDK v2 migration."""

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mcp_server.main import mcp


@pytest.mark.asyncio
async def test_server_negotiates_modern_and_legacy_protocols():
    async with Client(mcp) as modern_client:
        modern_tools = await modern_client.list_tools()
        assert modern_client.protocol_version == "2026-07-28"
        assert "salla_list_products" in {tool.name for tool in modern_tools.tools}
        assert all(tool.input_schema.get("type") == "object" for tool in modern_tools.tools)

    async with Client(mcp, mode="legacy") as legacy_client:
        legacy_tools = await legacy_client.list_tools()
        assert legacy_client.protocol_version != "2026-07-28"
        assert {tool.name for tool in legacy_tools.tools} == {
            tool.name for tool in modern_tools.tools
        }


@pytest.mark.asyncio
async def test_streamable_http_propagates_authorization_header():
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host="127.0.0.1",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    server_task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started

        with patch("mcp_server.utils.SallaClient") as salla_client_type:
            salla_client = AsyncMock()
            salla_client.get.return_value = {"data": {"id": 1, "name": "Store"}}
            salla_client_type.return_value = salla_client

            async with httpx2.AsyncClient(
                headers={"Authorization": "Bearer merchant-token"},
                timeout=httpx2.Timeout(5.0, read=30.0),
                follow_redirects=True,
            ) as http_client:
                transport = streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp",
                    http_client=http_client,
                )
                async with Client(transport, mode="auto") as client:
                    result = await client.call_tool("salla_get_store_info", {})
                    protocol_version = client.protocol_version

        assert protocol_version == "2026-07-28"
        assert result.is_error is False
        salla_client_type.assert_called_once_with(access_token="merchant-token")
        salla_client.get.assert_awaited_once_with("/store/info")
    finally:
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=5)
