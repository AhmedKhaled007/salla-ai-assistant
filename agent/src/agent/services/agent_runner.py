"""LLM tool-calling loop, independent of any tool transport."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from agent.core import logger, settings
from agent.services.llm import call_llm


MAX_ITERATIONS_MESSAGE = (
    "I couldn't complete that request. "
    "Try narrowing it down or splitting it into smaller parts."
)


class AgentRunner:
    """Run the LLM loop using tool schemas and an execution callback."""

    def __init__(
        self,
        max_iterations: int | None = None,
    ) -> None:
        self._max_iterations = (
            max_iterations if max_iterations is not None else settings.max_iterations
        )

    async def run(
        self,
        messages: list,
        tools: list,
        execute_tool,
    ) -> list:
        """Run the non-streaming agent loop and return the updated transcript."""
        working_messages = list(messages)
        iteration_count = 0

        while iteration_count < self._max_iterations:
            response = await call_llm(working_messages, tools=tools)
            response_message = response.choices[0].message
            tool_calls = getattr(response_message, "tool_calls", None)

            if tool_calls:
                working_messages.append(response_message.model_dump())
                for tool_call in tool_calls:
                    working_messages.append(
                        await self._execute_tool(execute_tool, tool_call)
                    )
                iteration_count += 1
                continue

            working_messages.append({
                "role": "assistant",
                "content": response_message.content,
            })
            return working_messages

        working_messages.append({
            "role": "assistant",
            "content": MAX_ITERATIONS_MESSAGE,
        })
        return working_messages

    async def stream(
        self,
        messages: list,
        tools: list,
        execute_tool,
    ) -> AsyncIterator[dict]:
        """Run the streaming agent loop and yield simple dictionary events."""
        working_messages = list(messages)
        iteration_count = 0

        while iteration_count < self._max_iterations:
            response = await call_llm(
                working_messages,
                tools=tools,
                stream=True,
            )
            current_content = ""
            tool_calls_buffer = {}

            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    current_content += delta.content
                    yield {"type": "response_chunk", "chunk": delta.content}
                if delta.tool_calls:
                    self._merge_tool_call_chunks(tool_calls_buffer, delta.tool_calls)

            tool_calls = [tool_calls_buffer[index] for index in sorted(tool_calls_buffer)]
            assistant_message = {
                "role": "assistant",
                "content": current_content or None,
            }
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            working_messages.append(assistant_message)
            yield {"type": "message", "message": assistant_message}

            if not tool_calls:
                yield {"type": "response", "content": current_content}
                yield {"type": "complete", "messages": working_messages}
                return

            for tool_call in tool_calls:
                name, arguments, _ = self._parse_tool_call(tool_call)
                yield {"type": "tool_call", "tool_name": name, "tool_args": arguments}
                tool_message = await self._execute_tool(execute_tool, tool_call)
                yield {
                    "type": "tool_result",
                    "tool_name": name,
                    "result": tool_message["content"],
                }
                working_messages.append(tool_message)
                yield {"type": "message", "message": tool_message}
            iteration_count += 1

        fallback_message = {
            "role": "assistant",
            "content": MAX_ITERATIONS_MESSAGE,
        }
        working_messages.append(fallback_message)
        yield {"type": "message", "message": fallback_message}
        yield {"type": "response", "content": MAX_ITERATIONS_MESSAGE}
        yield {"type": "complete", "messages": working_messages}

    @classmethod
    async def _execute_tool(
        cls,
        execute_tool,
        tool_call,
    ) -> dict:
        name, arguments, tool_call_id = cls._parse_tool_call(tool_call)
        logger.info("Executing tool: %s", name)
        output = await execute_tool(name, arguments)
        return {
            "role": "tool",
            "name": name,
            "tool_call_id": tool_call_id,
            "content": output,
        }

    @staticmethod
    def _parse_tool_call(tool_call) -> tuple[str, dict, str]:
        if isinstance(tool_call, dict):
            function = tool_call["function"]
            tool_call_id = tool_call["id"]
            name = function["name"]
            raw_arguments = function["arguments"]
        else:
            function = tool_call.function
            tool_call_id = tool_call.id
            name = function.name
            raw_arguments = function.arguments

        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise ValueError(f"Tool arguments for {name} must be a JSON object")
        return name, arguments, tool_call_id

    @staticmethod
    def _merge_tool_call_chunks(buffer, chunks) -> None:
        for chunk in chunks:
            index = chunk.index
            if index not in buffer:
                buffer[index] = {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            if chunk.id:
                buffer[index]["id"] += chunk.id
            if chunk.function:
                if chunk.function.name:
                    buffer[index]["function"]["name"] += chunk.function.name
                if chunk.function.arguments:
                    buffer[index]["function"]["arguments"] += chunk.function.arguments
