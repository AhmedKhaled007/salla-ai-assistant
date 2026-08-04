"""Tests for conversation orchestration around the agent runner."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.services.query_processor import QueryProcessor


def dependencies():
    mcp_client = MagicMock()
    mcp_connection = MagicMock()
    tools = [{"type": "function", "function": {"name": "lookup"}}]
    mcp_client.get_openai_tools = AsyncMock(return_value=tools)
    mcp_client.execute_tool = AsyncMock(return_value='{"ok": true}')

    @asynccontextmanager
    async def connect(token=None):
        yield mcp_connection

    mcp_client.connect.side_effect = connect

    conversation_service = MagicMock()
    conversation_service.create_conversation = AsyncMock(
        return_value="new-conversation-id"
    )
    conversation_service.get_history = AsyncMock(return_value=[])
    conversation_service.save_history = AsyncMock()
    conversation_service.add_message = AsyncMock()
    conversation_service.generate_title = AsyncMock(return_value="Greeting")
    conversation_service.update_title = AsyncMock()

    agent_runner = MagicMock()
    processor = QueryProcessor(mcp_client)
    processor.conversation_service = conversation_service
    processor.agent_runner = agent_runner
    processor._log_conversation = AsyncMock()
    return processor, conversation_service, agent_runner, mcp_client, mcp_connection


@pytest.mark.asyncio
async def test_process_query_creates_and_persists_conversation_when_id_is_missing():
    processor, conversations, runner, mcp_client, mcp_connection = dependencies()
    completed_messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"},
    ]

    async def run_agent(messages, tools, execute_tool):
        assert await execute_tool("lookup", {"id": 1}) == '{"ok": true}'
        return completed_messages

    runner.run = AsyncMock(side_effect=run_agent)

    conversation_id, messages = await processor.process_query("Hello", user_id=1)

    assert conversation_id == "new-conversation-id"
    assert messages == completed_messages[1:]
    conversations.create_conversation.assert_awaited_once_with(user_id=1)
    conversations.generate_title.assert_awaited_once_with("Hello")
    conversations.update_title.assert_awaited_once_with(
        "new-conversation-id",
        "Greeting",
    )
    conversations.save_history.assert_awaited_once_with(
        "new-conversation-id",
        completed_messages,
    )
    mcp_client.connect.assert_called_once_with(None)
    mcp_client.get_openai_tools.assert_awaited_once_with(mcp_connection)
    mcp_client.execute_tool.assert_awaited_once_with(
        mcp_connection,
        "lookup",
        {"id": 1},
    )
    runner.run.assert_awaited_once()
    assert runner.run.await_args.args[1] == [
        {"type": "function", "function": {"name": "lookup"}}
    ]


@pytest.mark.asyncio
async def test_process_query_loads_existing_conversation_and_forwards_token():
    processor, conversations, runner, mcp_client, _ = dependencies()
    history = [{"role": "user", "content": "Earlier"}]
    conversations.get_history.return_value = history
    completed = history + [
        {"role": "user", "content": "Continue"},
        {"role": "assistant", "content": "Done"},
    ]
    runner.run = AsyncMock(return_value=completed)

    await processor.process_query(
        "Continue",
        conversation_id="existing-id",
        token="merchant-token",
    )

    conversations.get_history.assert_awaited_once_with("existing-id")
    conversations.generate_title.assert_not_awaited()
    conversations.update_title.assert_not_awaited()
    mcp_client.connect.assert_called_once_with("merchant-token")


@pytest.mark.asyncio
async def test_process_query_stream_maps_events_and_persists_messages():
    processor, conversations, runner, mcp_client, _ = dependencies()
    assistant_message = {"role": "assistant", "content": "Hello"}
    completed_messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Hello"},
        assistant_message,
    ]

    async def agent_events(*args):
        yield {"type": "response_chunk", "chunk": "Hel"}
        yield {
            "type": "tool_call",
            "tool_name": "lookup",
            "tool_args": {"id": 1},
        }
        yield {
            "type": "tool_result",
            "tool_name": "lookup",
            "result": '{"ok": true}',
        }
        yield {"type": "message", "message": assistant_message}
        yield {"type": "response", "content": "Hello"}
        yield {"type": "complete", "messages": completed_messages}

    runner.stream.side_effect = agent_events

    events = [
        event
        async for event in processor.process_query_stream(
            "Hello",
            token="merchant-token",
            user_id=1,
        )
    ]

    assert events[:2] == [
        {"type": "conversation", "conversation_id": "new-conversation-id"},
        {"type": "title", "title": "Greeting"},
    ]
    assert {"type": "response_chunk", "chunk": "Hel"} in events
    assert {
        "type": "tool_call",
        "tool_name": "lookup",
        "tool_args": {"id": 1},
    } in events
    assert {"type": "response", "content": "Hello"} in events
    assert events[-1] == {
        "type": "done",
        "conversation_id": "new-conversation-id",
        "messages": completed_messages[1:],
    }
    conversations.update_title.assert_awaited_once_with(
        "new-conversation-id",
        "Greeting",
    )
    assert conversations.add_message.await_count == 3
    assert conversations.add_message.await_args_list[0].args[1]["role"] == "system"
    mcp_client.connect.assert_called_once_with("merchant-token")


@pytest.mark.asyncio
async def test_process_query_stream_emits_one_error_event():
    processor, _, runner, _, _ = dependencies()

    async def failed_agent(*args):
        raise RuntimeError("agent failed")
        yield

    runner.stream.side_effect = failed_agent

    events = [
        event
        async for event in processor.process_query_stream("Hello", user_id=1)
    ]

    assert [event for event in events if event["type"] == "error"] == [
        {"type": "error", "message": "agent failed"}
    ]
