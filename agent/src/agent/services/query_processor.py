"""Service for processing user queries using LLM and MCP tools."""

import json
import traceback
import contextvars
from typing import Optional, Any, AsyncGenerator
from datetime import datetime
import asyncio
import os
import aiofiles

from agent.core import settings, logger
from agent.services.prompts import SYSTEM_PROMPT
from agent.services.llm import call_llm
from agent.services.conversation import ConversationService
from agent.services.mcp_client import MCPClient


from agent.services.mcp_client import token_context

class QueryProcessor:
    """Service to process queries using LLM and MCP Client."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.conversation_service = ConversationService()

    async def process_query(self, query: str, conversation_id: str | None = None, token: Optional[str] = None, user_id: Optional[int] = None) -> list:
        """Process a user query using the LLM with tool access."""
        # Set token in context if provided
        token_reset = None
        if token:
            token_reset = token_context.set(token)

        try:
            # Ensure connection for this context
            await self.mcp_client.ping()

            # Load or initialize conversation
            messages = []
            if conversation_id:
                messages = await self.conversation_service.get_history(conversation_id)

            if not messages:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            messages.append({"role": "user", "content": query})

            # Get cached tools in OpenAI format
            openai_tools = self.mcp_client.get_openai_tools()

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
                        # We need to access execute_tool on mcp_client. 
                        # mcp_client._execute_tool_with_retry was private. We should make it public or expose a wrapper.
                        # For now, let's assume we rename it to execute_tool in mcp_client.
                        tool_output = await self.mcp_client.execute_tool(tool_name, tool_args)

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

            if conversation_id:
                await self.conversation_service.save_history(conversation_id, messages)
                await self._log_conversation(conversation_id, messages)

            return [msg for msg in messages if msg.get("role") != "system"]

        finally:
            if token_reset:
                token_context.reset(token_reset)

    async def process_query_stream(self, query: str, conversation_id: str | None = None, token: Optional[str] = None, user_id: Optional[int] = None) -> AsyncGenerator[dict[str, Any], None]:
        """Process a query with streaming, yielding events for each step."""
        token_reset = None
        if token:
            token_reset = token_context.set(token)

        try:
            try:
                await self.mcp_client.ping()

                messages = []
                if conversation_id:
                    messages = await self.conversation_service.get_history(conversation_id)
                else:
                    # user_id is required; use 0 or fetch properly if available
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

                messages.append({"role": "user", "content": query})
                openai_tools = self.mcp_client.get_openai_tools()
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
                                    tool_calls_buffer[idx] = {"id": "", "type": "function",
                                                              "function": {"name": "", "arguments": ""}}
                                if tc_chunk.id:
                                    tool_calls_buffer[idx]["id"] += tc_chunk.id
                                if tc_chunk.function:
                                    if tc_chunk.function.name:
                                        tool_calls_buffer[idx]["function"]["name"] += tc_chunk.function.name
                                    if tc_chunk.function.arguments:
                                        tool_calls_buffer[idx]["function"]["arguments"] += tc_chunk.function.arguments

                    tool_calls = [tool_calls_buffer[idx] for idx in sorted(tool_calls_buffer.keys())]
                    assistant_msg = {"role": "assistant", "content": current_content or None}
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    messages.append(assistant_msg)

                    if tool_calls:
                        for tool_call in tool_calls:
                            tool_name = tool_call["function"]["name"]
                            tool_args = json.loads(tool_call["function"]["arguments"])
                            yield {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args}

                            tool_output = await self.mcp_client.execute_tool(tool_name, tool_args)
                            yield {"type": "tool_result", "tool_name": tool_name, "result": tool_output}

                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call["id"],
                                "content": tool_output
                            })
                        iteration_count += 1
                    else:
                        yield {"type": "response", "content": current_content}
                        break

                await self.conversation_service.save_history(conversation_id, messages)
                await self._log_conversation(conversation_id, messages)

                filtered_messages = [msg for msg in messages if msg.get("role") != "system"]
                yield {"type": "done", "session_id": conversation_id, "messages": filtered_messages}
            except Exception as e:
                logger.error(f"Error in process_query_stream: {e}")
                logger.error(traceback.format_exc())
                yield {"type": "error", "message": str(e)}
                raise

        finally:
            if token_reset:
                token_context.reset(token_reset)

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
