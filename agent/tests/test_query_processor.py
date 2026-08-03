from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.services.query_processor import QueryProcessor


@pytest.mark.asyncio
async def test_process_query_creates_and_persists_conversation_when_id_is_missing():
    mcp_client = MagicMock()
    connection = MagicMock()
    mcp_client.get_openai_tools = AsyncMock(return_value=[])

    @asynccontextmanager
    async def connect(token=None):
        yield connection

    mcp_client.connect.side_effect = connect

    processor = QueryProcessor(mcp_client)
    processor.conversation_service = MagicMock()
    processor.conversation_service.create_conversation = AsyncMock(
        return_value="new-conversation-id"
    )
    processor.conversation_service.save_history = AsyncMock()
    processor._log_conversation = AsyncMock()

    llm_response = MagicMock()
    llm_response.choices[0].message.tool_calls = None
    llm_response.choices[0].message.content = "Hello!"

    with patch("agent.services.query_processor.call_llm", new=AsyncMock(return_value=llm_response)):
        conversation_id, messages = await processor.process_query("Hello", user_id=1)

    assert conversation_id == "new-conversation-id"
    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"},
    ]
    processor.conversation_service.create_conversation.assert_awaited_once_with(user_id=1)
    processor.conversation_service.save_history.assert_awaited_once()
    mcp_client.connect.assert_called_once_with(None)
    mcp_client.get_openai_tools.assert_awaited_once_with(connection)
    saved_conversation_id, saved_messages = processor.conversation_service.save_history.await_args.args
    assert saved_conversation_id == "new-conversation-id"
    assert saved_messages[0]["role"] == "system"


@pytest.mark.asyncio
async def test_process_query_stream_uses_one_token_scoped_connection():
    mcp_client = MagicMock()
    connection = MagicMock()
    mcp_client.get_openai_tools = AsyncMock(return_value=[])

    @asynccontextmanager
    async def connect(token=None):
        yield connection

    mcp_client.connect.side_effect = connect
    processor = QueryProcessor(mcp_client)
    processor.conversation_service = MagicMock()
    processor.conversation_service.create_conversation = AsyncMock(return_value="conversation-id")
    processor.conversation_service.generate_title = AsyncMock(return_value="Greeting")
    processor.conversation_service.update_title = AsyncMock()
    processor.conversation_service.add_message = AsyncMock()
    processor._log_conversation = AsyncMock()

    chunk = MagicMock()
    chunk.choices[0].delta.content = "Hello"
    chunk.choices[0].delta.tool_calls = None

    async def chunks():
        yield chunk

    with patch("agent.services.query_processor.call_llm", new=AsyncMock(return_value=chunks())):
        events = [
            event
            async for event in processor.process_query_stream(
                "Hello",
                token="merchant-token",
                user_id=1,
            )
        ]

    assert any(event == {"type": "response", "content": "Hello"} for event in events)
    assert events[-1]["type"] == "done"
    mcp_client.connect.assert_called_once_with("merchant-token")
    mcp_client.get_openai_tools.assert_awaited_once_with(connection)
