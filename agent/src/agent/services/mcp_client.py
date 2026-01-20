"""MCP (Model Context Protocol) client for communicating with tool servers.

This module implements the core agent logic:
1. Connects to MCP servers (via stdio or HTTP)
2. Maintains conversation history
3. Processes user queries using LLMs (via LiteLLM)
4. Executes tools exposed by the MCP server
5. Manages token isolation (via headers/env vars)
"""

from typing import Optional
from contextlib import AsyncExitStack
import asyncio
import traceback
import json
import os
import uuid
from datetime import datetime
from httpx import ConnectError, TimeoutException as HttpxTimeoutException

import aiofiles

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
import litellm

from ..core import settings, logger
from .prompts import SYSTEM_PROMPT
from .llm import call_llm
from .conversation import ConversationService


class MCPClient:
    """MCP (Model Context Protocol) client for communicating with tool servers.

    This client connects to an MCP server via stdio and provides methods for:
    - Processing user queries using an LLM with tool access
    - Maintaining conversation history
    - Executing tools on the MCP server
    """

    def __init__(self, transport: str = "stdio", server_url: Optional[str] = None, user_id: Optional[int] = None):
        """Initialize the MCP client.

        Args:
            transport: Transport type - 'stdio' or 'sse'
            server_url: URL for SSE transport (e.g., 'http://localhost:8001/sse')
            user_id: Optional user ID for conversation persistence
        """
        # Session state
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

        # Configuration
        self.transport = transport
        self.server_url = server_url or settings.mcp_server_url

        # Salla Access Token (for authentication context)
        self._access_token: Optional[str] = None
        self.user_id = user_id

        # Cached tool definitions (refreshed on connect/reconnect)
        self._cached_tools: Optional[list] = None
        self._cached_openai_tools: Optional[list] = None

        # Repositories / Services
        self.conversation_service = ConversationService()

    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        tool_args: dict,
        max_retries: int = 2,
    ) -> str:
        """Execute a tool call with timeout and retry logic.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool
            max_retries: Maximum number of retry attempts for transient failures

        Returns:
            Tool output as string

        Raises:
            asyncio.TimeoutError: If tool execution times out after all retries
            Exception: Other errors from tool execution
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self.session.call_tool(tool_name, tool_args),
                    timeout=settings.tool_timeout
                )

                # Format result text
                if hasattr(result, 'content') and result.content:
                    return "\n".join([c.text for c in result.content if c.type == 'text'])
                return str(result)

            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Tool {tool_name} timed out (attempt {attempt + 1}/{max_retries + 1}), retrying..."
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                else:
                    raise asyncio.TimeoutError(
                        f"Tool {tool_name} timed out after {settings.tool_timeout}s"
                    )

            except (ConnectError, HttpxTimeoutException, ConnectionError, OSError) as e:
                # Transient network errors - retry
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Tool {tool_name} failed with {type(e).__name__} "
                        f"(attempt {attempt + 1}/{max_retries + 1}), retrying..."
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    raise

            except Exception as e:
                # Non-retryable errors (4xx client errors, validation errors, etc.)
                raise

    def is_connected(self) -> bool:
        """Check if the MCP server connection is active."""
        return self.session is not None

    async def ping(self) -> bool:
        """Ping the MCP server to check if it's responsive.

        Returns:
            True if server responds, False otherwise.
        """
        try:
            if not self.session:
                return False

            # List tools is a cheap operation to check connectivity
            await self.session.list_tools()
            return True
        except Exception:
            return False

    async def ensure_connected(self) -> bool:
        """Ensure connection to MCP server, reconnecting if necessary.

        Returns:
            True if connected (or reconnected successfully).

        Raises:
            RuntimeError: If reconnection fails.
        """
        if self.is_connected():
            return True

        logger.info("Connection lost or not established, reconnecting...")

        # Determine connection parameters
        server_path = settings.server_script_path

        if self.transport == "sse" or self.transport == "http":
            success = await self._connect_http()
        else:
            success = await self._connect_stdio(server_path, self._access_token)

        if not success:
            raise RuntimeError("Failed to reconnect to MCP server")

        return True

    async def set_access_token(self, access_token: str) -> bool:
        """Update the Salla access token.

        For SSE transport, this just updates the token for future requests.
        For stdio transport, this reconnects the MCP server with new env.

        Args:
            access_token: The new Salla OAuth access token.

        Returns:
            True if update was successful.
        """
        self._access_token = access_token

        if self.transport == "stdio":
            # For stdio, we must restart the process to update env vars
            server_path = settings.server_script_path
            # Disconnect logic
            if self.session:
                try:
                    await self.exit_stack.aclose()
                    self.session = None
                except Exception as e:
                    logger.warning(f"Error disconnecting while setting token: {e}")

            return await self._connect_stdio(server_path, access_token)

        # For HTTP/SSE, token is passed in headers per request, no need to reconnect
        return True

    async def connect_to_server(self, server_script_path: str = "", access_token: Optional[str] = None) -> bool:
        """Connect to an MCP server.

        Args:
            server_script_path: Path to server script (for stdio) or ignored (for SSE).
            access_token: Optional Salla OAuth access token.

        Returns:
            True if connection was successful.
        """
        self._access_token = access_token

        if self.transport == "sse" or self.transport == "http":
            return await self._connect_http()
        else:  # stdio
            # Use configured path if not provided
            path = server_script_path or settings.server_script_path
            return await self._connect_stdio(path, access_token)

    async def _connect_http(self) -> bool:
        """Connect to MCP server via Streamable HTTP transport."""
        try:
            # Prepare headers with access token if available
            headers = {}
            if self._access_token:
                headers["Authorization"] = f"Bearer {self._access_token}"

            server_params = self.server_url

            # Connect via SSE - this returns streams, not a session
            read_stream, write_stream, _ = await self.exit_stack.enter_async_context(
                streamablehttp_client(server_params, headers=headers)
            )

            # Create session using streams
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            await self._load_tools()
            logger.info(f"Connected to MCP server via HTTP/SSE at {self.server_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server via HTTP: {e}")
            logger.error(traceback.format_exc())
            return False

    async def _connect_stdio(self, server_script_path: str, access_token: Optional[str] = None) -> bool:
        """Connect to MCP server via stdio transport."""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js') or server_script_path.endswith('.ts')

        if not is_python and not is_js:
            logger.error("Unknown server script type")
            return False

        command = "python" if is_python else "node"
        args = [server_script_path]

        # Prepare environment
        env = os.environ.copy()
        if access_token:
            env["SALLA_ACCESS_TOKEN"] = access_token

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        try:
            self.session = await self.exit_stack.enter_async_context(stdio_client(server_params))
            await self._load_tools()
            logger.info(f"Connected to MCP server via stdio: {command} {server_script_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server via stdio: {e}")
            return False

    async def _load_tools(self):
        """Load available tools from MCP server and cache them."""
        if not self.session:
            return

        try:
            # Just initialize connection/handshake
            await self.session.initialize()

            # Load and cache tools
            tools_result = await self.session.list_tools()
            self._cached_tools = tools_result.tools

            # Also cache in OpenAI format for LLM calls
            self._cached_openai_tools = []
            for tool in self._cached_tools:
                self._cached_openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            tool_names = [t.name for t in self._cached_tools]
            logger.debug(f"Loaded and cached {len(tool_names)} tools: {tool_names}")

        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            raise

    def _get_openai_tools(self) -> list:
        """Get cached OpenAI-format tools.

        Returns:
            List of tools in OpenAI function calling format.

        Raises:
            RuntimeError: If tools haven't been loaded yet.
        """
        if self._cached_openai_tools is None:
            raise RuntimeError("Tools not loaded. Call ensure_connected() first.")
        return self._cached_openai_tools

    async def get_mcp_tools(self):
        """Get the list of available tools from the MCP server.

        Uses cached tools if available.

        Returns:
            List of Tool objects from the MCP server.

        Raises:
            Exception: If retrieving tools fails.
        """
        await self.ensure_connected()
        if self._cached_tools is not None:
            return self._cached_tools
        result = await self.session.list_tools()
        return result.tools

    async def process_query(self, query: str, conversation_id: str | None = None) -> list:
        """Process a user query using the LLM with tool access.

        This method sends the query to the LLM, handles any tool calls,
        and returns the complete conversation. If a conversation_id is provided,
        it uses the existing conversation context.

        Args:
            query: The user's query string.
            conversation_id: Optional conversation ID to continue a conversation.

        Returns:
            List of message dictionaries representing the conversation.
            Structure:
            [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]

        Raises:
            Exception: If LLM call or tool execution fails.
        """
        # Ensure connection first
        await self.ensure_connected()

        # Load or initialize conversation
        messages = []
        if conversation_id:
            messages = await self.conversation_service.get_history(conversation_id)

        if not messages:
            # Basic system prompt if no history
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add user query
        messages.append({"role": "user", "content": query})

        # Get cached tools in OpenAI format
        openai_tools = self._get_openai_tools()

        # Process with tool loop
        iteration_count = 0
        final_response = None

        while iteration_count < settings.max_iterations:
            try:
                # Call LLM
                response = await call_llm(messages, tools=openai_tools)
                message = response.choices[0].message

                # Check for tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    messages.append(message.model_dump())

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        tool_call_id = tool_call.id

                        logger.info(f"Executing tool: {tool_name} with args: {tool_args_str}")

                        try:
                            tool_args = json.loads(tool_args_str)

                            # Execute on MCP server with retry and timeout
                            tool_output = await self._execute_tool_with_retry(tool_name, tool_args)

                            # Add result to history
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": tool_output
                            })

                        except json.JSONDecodeError as e:
                            error_msg = f"Invalid JSON in tool arguments for {tool_name}: {str(e)}"
                            logger.error(error_msg)
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except asyncio.TimeoutError as e:
                            error_msg = f"Tool {tool_name} timed out: {str(e)}"
                            logger.error(error_msg)
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except (ConnectError, HttpxTimeoutException, ConnectionError) as e:
                            error_msg = f"Network error executing tool {tool_name}: {type(e).__name__} - {str(e)}"
                            logger.error(error_msg)
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except Exception as e:
                            error_msg = f"Error executing tool {tool_name}: {str(e)}"
                            logger.error(error_msg)
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })

                    iteration_count += 1
                    # Continue loop to let LLM see results and potentially respond or call more tools

                else:
                    # No tool calls, just a text response
                    final_response = message.content
                    messages.append({"role": "assistant", "content": final_response})
                    break

            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                raise

        if not final_response and iteration_count >= settings.max_iterations:
            timeout_msg = "I'm sorry, I needed too many steps to complete this request."
            messages.append({"role": "assistant", "content": timeout_msg})

        # Save conversation locally (for debugging/logs)
        if conversation_id:
            await self.conversation_service.save_history(conversation_id, messages)

            # Also log to file system for debugging
            await self._log_conversation(conversation_id, messages)

        # Filter out system messages before returning to client
        return [msg for msg in messages if msg.get("role") != "system"]

    async def process_query_stream(self, query: str, conversation_id: str | None = None):
        """Process a query with streaming, yielding events for each step.

        Yields dictionaries with event types:
        - {"type": "conversation", "conversation_id": str}
        - {"type": "tool_call", "tool_name": str, "tool_args": dict}
        - {"type": "tool_result", "tool_name": str, "result": str}
        - {"type": "response", "content": str}
        - {"type": "error", "message": str}
        - {"type": "done", "conversation_id": str}
        """
        await self.ensure_connected()

        # Load or initialize conversation
        messages = []
        if conversation_id:
            messages = await self.conversation_service.get_history(conversation_id)
        else:
            if not self.user_id:
                yield {"type": "error", "message": "Cannot auto-create conversation: User ID not provided"}
                return
            conversation_id = await self.conversation_service.create_conversation(user_id=self.user_id)

        yield {"type": "conversation", "conversation_id": conversation_id}

        if not messages:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            title = None
            try:
                # Generate title for new conversations
                title = await self.conversation_service.generate_title(query)
                # Update title in background to not block too much, or await?
                # User asked to "make request ... before run the mcp client"
                # So we await generation, but maybe async save
                await self.conversation_service.update_title(conversation_id, title)
                logger.info(f"Set conversation {conversation_id} title to: {title}")
            except Exception as e:
                logger.warning(f"Failed to set conversation title: {e}")

            if title:
                yield {"type": "title", "title": title}
        messages.append({"role": "user", "content": query})

        # Get cached tools in OpenAI format
        openai_tools = self._get_openai_tools()

        iteration_count = 0

        while iteration_count < settings.max_iterations:
            try:
                # Call LLM with streaming
                response = await call_llm(messages, tools=openai_tools, stream=True)

                current_content = ""
                tool_calls_buffer = {}  # index -> data

                async for chunk in response:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    if delta.content:
                        content_chunk = delta.content
                        current_content += content_chunk
                        yield {"type": "response_chunk", "chunk": content_chunk}

                    if delta.tool_calls:
                        for tc_chunk in delta.tool_calls:
                            idx = tc_chunk.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }

                            if tc_chunk.id:
                                tool_calls_buffer[idx]["id"] += tc_chunk.id
                            if tc_chunk.function:
                                if tc_chunk.function.name:
                                    tool_calls_buffer[idx]["function"]["name"] += tc_chunk.function.name
                                if tc_chunk.function.arguments:
                                    tool_calls_buffer[idx]["function"]["arguments"] += tc_chunk.function.arguments

                # Reconstruct full list of tool calls
                tool_calls = []
                for idx in sorted(tool_calls_buffer.keys()):
                    tool_calls.append(tool_calls_buffer[idx])

                # Create assistant message
                assistant_msg = {
                    "role": "assistant",
                    "content": current_content or None
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                messages.append(assistant_msg)

                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call["function"]["name"]
                        tool_args_str = tool_call["function"]["arguments"]
                        tool_call_id = tool_call["id"]

                        try:
                            tool_args = json.loads(tool_args_str)

                            yield {
                                "type": "tool_call",
                                "tool_name": tool_name,
                                "tool_args": tool_args
                            }

                            # Execute on MCP server with retry and timeout
                            tool_output = await self._execute_tool_with_retry(tool_name, tool_args)

                            yield {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "result": tool_output
                            }

                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": tool_output
                            })

                        except json.JSONDecodeError as e:
                            error_msg = f"Invalid JSON in tool arguments for {tool_name}: {str(e)}"
                            logger.error(error_msg)
                            yield {"type": "error", "message": error_msg}
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except asyncio.TimeoutError as e:
                            error_msg = f"Tool {tool_name} timed out: {str(e)}"
                            logger.error(error_msg)
                            yield {"type": "error", "message": error_msg}
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except (ConnectError, HttpxTimeoutException, ConnectionError) as e:
                            error_msg = f"Network error executing tool {tool_name}: {type(e).__name__} - {str(e)}"
                            logger.error(error_msg)
                            yield {"type": "error", "message": error_msg}
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })
                        except Exception as e:
                            error_msg = f"Error executing tool {tool_name}: {str(e)}"
                            logger.error(error_msg)
                            yield {"type": "error", "message": error_msg}
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": error_msg
                            })

                    iteration_count += 1

                else:
                    # Final text response done
                    yield {"type": "response", "content": current_content}
                    break

            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return

        # Save session
        await self.conversation_service.save_history(conversation_id, messages)
        await self._log_conversation(conversation_id, messages)

        # Filter out system messages from final messages list
        filtered_messages = [msg for msg in messages if msg.get("role") != "system"]
        yield {"type": "done", "session_id": conversation_id, "messages": filtered_messages}

    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.exit_stack.aclose()
            self.session = None

    async def _log_conversation(self, conversation_id: str, messages: list):
        """Save conversation to a JSON file asynchronously."""
        try:
            log_dir = settings.conversation_log_dir
            os.makedirs(log_dir, exist_ok=True)

            # Format filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{log_dir}/{conversation_id}_{timestamp}.json"

            # Sanitize messages to not include huge unrelated data if any
            # (Pydantic models might need dumping)
            serializable_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    serializable_messages.append(msg)
                else:
                    # Handle cases where msg might be an object
                    try:
                        serializable_messages.append(dict(msg))
                except (TypeError, ValueError, AttributeError):
                    serializable_messages.append(str(msg))

            async with aiofiles.open(filename, mode='w') as f:
                await f.write(json.dumps(serializable_messages, indent=2, ensure_ascii=False))

        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")
