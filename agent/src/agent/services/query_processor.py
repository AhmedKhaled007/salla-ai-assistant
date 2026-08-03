"""Service for processing user queries using LLM and MCP tools."""

import json
import traceback
from typing import Optional, Any, AsyncGenerator
from datetime import datetime
import os
import aiofiles

from agent.core import settings, logger
from agent.services.prompts import SYSTEM_PROMPT
from agent.services.llm import call_llm
from agent.services.conversation import ConversationService
from agent.services.mcp_client import MCPClient

class QueryProcessor:
    """Service to process queries using LLM and MCP Client."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.conversation_service = ConversationService()

    async def process_query(self, query: str, conversation_id: str | None = None, token: Optional[str] = None, user_id: Optional[int] = None) -> tuple[str, list]:
        """Process a query and return its conversation ID and messages."""
        messages = []
        if conversation_id:
            messages = await self.conversation_service.get_history(conversation_id)
        else:
            if user_id is None:
                raise ValueError("user_id is required when creating a conversation")
            conversation_id = await self.conversation_service.create_conversation(user_id=user_id)

        if not messages:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        messages.append({"role": "user", "content": query})

        async with self.mcp_client.connect(token) as mcp_client:
            openai_tools = await self.mcp_client.get_openai_tools(mcp_client)
            iteration_count = 0
            final_response = None

            while iteration_count < settings.max_iterations:
                response = await call_llm(messages, tools=openai_tools)
                message = response.choices[0].message

                if hasattr(message, 'tool_calls') and message.tool_calls:
                    messages.append(message.model_dump())

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        logger.info(f"Executing tool: {tool_name}")
                        tool_output = await self.mcp_client.execute_tool(
                            mcp_client,
                            tool_name,
                            tool_args,
                        )

                        messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "tool_call_id": tool_call.id,
                            "content": tool_output
                        })
                    iteration_count += 1
                else:
                    final_response = message.content
                    messages.append({"role": "assistant", "content": final_response})
                    break

        if not final_response and iteration_count >= settings.max_iterations:
            messages.append(
                {"role": "assistant", "content": "I'm sorry, I needed too many steps to complete this request."})

        await self.conversation_service.save_history(conversation_id, messages)
        await self._log_conversation(conversation_id, messages)

        return conversation_id, [msg for msg in messages if msg.get("role") != "system"]

    async def process_query_stream(self, query: str, conversation_id: str | None = None, token: Optional[str] = None, user_id: Optional[int] = None) -> AsyncGenerator[dict[str, Any], None]:
        """Process a query with streaming, yielding events for each step."""
        try:
            messages = []
            if conversation_id:
                messages = await self.conversation_service.get_history(conversation_id)
            else:
                if user_id is None:
                    raise ValueError("user_id is required when creating a conversation")
                conversation_id = await self.conversation_service.create_conversation(user_id=user_id)

            yield {"type": "conversation", "conversation_id": conversation_id}

            if not messages:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                try:
                    title = await self.conversation_service.generate_title(query)
                    await self.conversation_service.update_title(conversation_id, title)
                    yield {"type": "title", "title": title}
                except Exception:
                    pass

            user_msg = {"role": "user", "content": query}
            messages.append(user_msg)
            await self.conversation_service.add_message(conversation_id, user_msg)

            async with self.mcp_client.connect(token) as mcp_client:
                openai_tools = await self.mcp_client.get_openai_tools(mcp_client)
                iteration_count = 0

                while iteration_count < settings.max_iterations:
                    response = await call_llm(messages, tools=openai_tools, stream=True)
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
                            for tc_chunk in delta.tool_calls:
                                idx = tc_chunk.index
                                if idx not in tool_calls_buffer:
                                    tool_calls_buffer[idx] = {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                if tc_chunk.id:
                                    tool_calls_buffer[idx]["id"] += tc_chunk.id
                                if tc_chunk.function:
                                    if tc_chunk.function.name:
                                        tool_calls_buffer[idx]["function"]["name"] += tc_chunk.function.name
                                    if tc_chunk.function.arguments:
                                        tool_calls_buffer[idx]["function"]["arguments"] += tc_chunk.function.arguments

                    tool_calls = [tool_calls_buffer[idx] for idx in sorted(tool_calls_buffer)]
                    assistant_msg = {"role": "assistant", "content": current_content or None}
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    messages.append(assistant_msg)
                    await self.conversation_service.add_message(conversation_id, assistant_msg)

                    if tool_calls:
                        for tool_call in tool_calls:
                            tool_name = tool_call["function"]["name"]
                            tool_args = json.loads(tool_call["function"]["arguments"])
                            yield {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args}

                            tool_output = await self.mcp_client.execute_tool(
                                mcp_client,
                                tool_name,
                                tool_args,
                            )
                            yield {"type": "tool_result", "tool_name": tool_name, "result": tool_output}

                            tool_msg = {
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call["id"],
                                "content": tool_output,
                            }
                            messages.append(tool_msg)
                            await self.conversation_service.add_message(conversation_id, tool_msg)
                        iteration_count += 1
                    else:
                        yield {"type": "response", "content": current_content}
                        break

            await self._log_conversation(conversation_id, messages)

            filtered_messages = [msg for msg in messages if msg.get("role") != "system"]
            yield {"type": "done", "session_id": conversation_id, "messages": filtered_messages}
        except Exception as e:
            logger.error(f"Error in process_query_stream: {e}")
            logger.error(traceback.format_exc())
            yield {"type": "error", "message": str(e)}
            raise

    async def _log_conversation(self, conversation_id: str, messages: list):
        """Save conversation to a JSON file asynchronously."""
        if not settings.conversation_log_enabled:
            return
        try:
            log_dir = settings.conversation_log_dir
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{log_dir}/{conversation_id}_{timestamp}.json"

            serializable_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    serializable_messages.append(msg)
                else:
                    try:
                        serializable_messages.append(dict(msg))
                    except (TypeError, ValueError, AttributeError):
                        serializable_messages.append(str(msg))

            async with aiofiles.open(filename, mode='w') as f:
                await f.write(json.dumps(serializable_messages, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")
