"""Tests for the transport-neutral LLM agent runner."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agent.services.agent_runner import AgentRunner, MAX_ITERATIONS_MESSAGE


def llm_message(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    message.model_dump = lambda: {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in tool_calls or []
        ],
    }
    return message


def llm_response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(name="lookup", arguments='{"id": 1}', call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


TOOLS = [{
    "type": "function",
    "function": {
        "name": "lookup",
        "description": "Look up an item",
        "parameters": {"type": "object"},
    },
}]


@pytest.mark.asyncio
async def test_run_returns_direct_response_and_passes_tools_to_llm():
    llm = AsyncMock(return_value=llm_response(llm_message(content="Hello")))
    execute_tool = AsyncMock()

    with patch("agent.services.agent_runner.call_llm", new=llm):
        result = await AgentRunner().run(
            [{"role": "user", "content": "Hi"}],
            TOOLS,
            execute_tool,
        )

    assert result[-1] == {"role": "assistant", "content": "Hello"}
    assert llm.await_args.kwargs["tools"] == TOOLS


@pytest.mark.asyncio
async def test_run_executes_multiple_tool_calls_then_finishes():
    calls = [
        tool_call(call_id="call-1"),
        tool_call(arguments='{"id": 2}', call_id="call-2"),
    ]
    llm = AsyncMock(side_effect=[
        llm_response(llm_message(tool_calls=calls)),
        llm_response(llm_message(content="Done")),
    ])
    execute_tool = AsyncMock(return_value='{"ok": true}')

    with patch("agent.services.agent_runner.call_llm", new=llm):
        result = await AgentRunner().run([], TOOLS, execute_tool)

    assert execute_tool.await_args_list[0].args == ("lookup", {"id": 1})
    assert execute_tool.await_args_list[1].args == ("lookup", {"id": 2})
    assert [message["role"] for message in result] == [
        "assistant",
        "tool",
        "tool",
        "assistant",
    ]
    assert result[-1]["content"] == "Done"


@pytest.mark.asyncio
async def test_run_propagates_tool_errors():
    llm = AsyncMock(return_value=llm_response(
        llm_message(tool_calls=[tool_call()])
    ))
    execute_tool = AsyncMock(side_effect=RuntimeError("tool failed"))

    with (
        patch("agent.services.agent_runner.call_llm", new=llm),
        pytest.raises(RuntimeError, match="tool failed"),
    ):
        await AgentRunner().run([], TOOLS, execute_tool)


@pytest.mark.asyncio
async def test_run_rejects_malformed_tool_arguments():
    llm = AsyncMock(return_value=llm_response(
        llm_message(tool_calls=[tool_call(arguments="not-json")])
    ))

    with (
        patch("agent.services.agent_runner.call_llm", new=llm),
        pytest.raises(ValueError),
    ):
        await AgentRunner().run([], TOOLS, AsyncMock())


@pytest.mark.asyncio
async def test_run_adds_fallback_at_iteration_limit():
    llm = AsyncMock(return_value=llm_response(
        llm_message(tool_calls=[tool_call()])
    ))

    with patch("agent.services.agent_runner.call_llm", new=llm):
        result = await AgentRunner(max_iterations=1).run(
            [],
            TOOLS,
            AsyncMock(return_value='{"ok": true}'),
        )

    assert result[-1]["content"] == MAX_ITERATIONS_MESSAGE
    assert result[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_stream_emits_fallback_at_iteration_limit():
    async def tool_chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(
                index=0,
                id="call-1",
                function=SimpleNamespace(name="lookup", arguments='{"id": 1}'),
            )],
        ))])

    llm = AsyncMock(return_value=tool_chunks())

    with patch("agent.services.agent_runner.call_llm", new=llm):
        events = [
            event
            async for event in AgentRunner(max_iterations=1).stream(
                [],
                TOOLS,
                AsyncMock(return_value='{"ok": true}'),
            )
        ]

    assert events[-3] == {
        "type": "message",
        "message": {"role": "assistant", "content": MAX_ITERATIONS_MESSAGE},
    }
    assert events[-2] == {
        "type": "response",
        "content": MAX_ITERATIONS_MESSAGE,
    }
    assert events[-1]["type"] == "complete"
    assert events[-1]["messages"][-1]["content"] == MAX_ITERATIONS_MESSAGE


@pytest.mark.asyncio
async def test_stream_reconstructs_tool_call_and_emits_completed_messages():
    async def tool_chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(
                index=0,
                id="call-1",
                function=SimpleNamespace(name="lookup", arguments='{"id":'),
            )],
        ))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(
                index=0,
                id=None,
                function=SimpleNamespace(name=None, arguments=" 1}"),
            )],
        ))])

    async def response_chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content="Done",
            tool_calls=None,
        ))])

    streams = [tool_chunks(), response_chunks()]

    async def llm(*args, **kwargs):
        return streams.pop(0)

    execute_tool = AsyncMock(return_value='{"ok": true}')
    with patch("agent.services.agent_runner.call_llm", new=llm):
        events = [
            event
            async for event in AgentRunner().stream(
                [],
                TOOLS,
                execute_tool,
            )
        ]

    assert {
        "type": "tool_call",
        "tool_name": "lookup",
        "tool_args": {"id": 1},
    } in events
    assert {
        "type": "tool_result",
        "tool_name": "lookup",
        "result": '{"ok": true}',
    } in events
    assert {"type": "response_chunk", "chunk": "Done"} in events
    assert {"type": "response", "content": "Done"} in events
    assert len([event for event in events if event["type"] == "message"]) == 3
    completed = next(event for event in events if event["type"] == "complete")
    assert completed["messages"][-1]["content"] == "Done"
