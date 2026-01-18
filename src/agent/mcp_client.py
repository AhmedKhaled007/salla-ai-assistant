from typing import Optional
from contextlib import AsyncExitStack
import asyncio
import traceback
import json
import os
import uuid
from datetime import datetime

import aiofiles

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import litellm

from .utils import settings, logger
from .prompts import SYSTEM_PROMPT



class MCPClient:
    """MCP (Model Context Protocol) client for communicating with tool servers.
    
    This client connects to an MCP server via stdio and provides methods for:
    - Processing user queries using an LLM with tool access
    - Managing conversation sessions for multi-turn interactions
    - Streaming responses for real-time UI updates
    
    Attributes:
        session: The MCP ClientSession for communicating with the server.
        tools: List of available tools from the MCP server.
    
    Example:
        ```python
        client = MCPClient()
        await client.connect_to_server("path/to/server.py")
        session_id, messages = await client.process_query("Hello!")
        await client.cleanup()
        ```
    """
    
    def __init__(self) -> None:
        """Initialize the MCP client with empty session and tools."""
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self.tools: list[dict] = []
        self._sessions: dict[str, list[dict]] = {}  # session_id -> messages
        self._lock: asyncio.Lock = asyncio.Lock()  # Serialize concurrent requests
        self._conversation_id: str = ""
        self._server_script_path: str = ""  # Store for reconnection

    @property
    def is_connected(self) -> bool:
        """Check if the MCP server connection is active."""
        return self.session is not None

    async def ping(self) -> bool:
        """Ping the MCP server to check if it's responsive.
        
        Returns:
            True if server responds, False otherwise.
        """
        if not self.session:
            return False
        try:
            # Try to list tools as a health check
            await asyncio.wait_for(self.session.list_tools(), timeout=5.0)
            return True
        except Exception as e:
            logger.warning(f"MCP server ping failed: {e}")
            return False

    async def ensure_connected(self) -> bool:
        """Ensure connection to MCP server, reconnecting if necessary.
        
        Returns:
            True if connected (or reconnected successfully).
        
        Raises:
            RuntimeError: If reconnection fails.
        """
        if await self.ping():
            return True
        
        if not self._server_script_path:
            raise RuntimeError("Cannot reconnect: no server script path stored")
        
        logger.warning("MCP server connection lost, attempting to reconnect...")
        
        # Cleanup and reconnect
        try:
            await self.cleanup()
        except Exception:
            pass  # Ignore cleanup errors
        
        # Reset state
        self.exit_stack = AsyncExitStack()
        self.session = None
        
        return await self.connect_to_server(self._server_script_path)

    def create_session(self) -> str:
        """Create a new conversation session and return its ID."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> list | None:
        """Get messages for a session. Returns None if session doesn't exist."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())

    async def connect_to_server(self, server_script_path: str) -> bool:
        """Connect to an MCP server.
        
        Args:
            server_script_path: Path to the server script (.py or .js file).
        
        Returns:
            True if connection was successful.
        
        Raises:
            ValueError: If server script is not a .py or .js file.
            Exception: If connection fails.
        """
        try:
            # Store path for potential reconnection
            self._server_script_path = server_script_path
            
            is_python = server_script_path.endswith(".py")
            is_js = server_script_path.endswith(".js")
            if not (is_python or is_js):
                raise ValueError("Server script must be a .py or .js file")

            command = "python" if is_python else "node"
            server_params = StdioServerParameters(
                command=command, args=[server_script_path], env=None
            )

            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )

            await self.session.initialize()

            logger.info("Connected to MCP server")

            mcp_tools = await self.get_mcp_tools()
            self.tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                }
                for tool in mcp_tools
            ]

            logger.info(
                f"Available tools: {[tool['function']['name'] for tool in self.tools]}"
            )

            return True

        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            traceback.print_exc()
            raise

    async def get_mcp_tools(self) -> list:
        """Get the list of available tools from the MCP server.
        
        Returns:
            List of Tool objects from the MCP server.
        
        Raises:
            Exception: If retrieving tools fails.
        """
        try:
            response = await self.session.list_tools()
            return response.tools
        except Exception as e:
            logger.error(f"Error getting MCP tools: {e}")
            raise

    async def process_query(
        self, query: str, session_id: str | None = None
    ) -> tuple[str, list[dict]]:
        """Process a user query using the LLM with tool access.
        
        This method sends the query to the LLM, handles any tool calls,
        and returns the complete conversation. If a session_id is provided,
        the conversation continues from the existing session history.
        
        Args:
            query: The user's query text.
            session_id: Optional session ID to continue an existing conversation.
                       If None, a new session is created automatically.
        
        Returns:
            A tuple of (session_id, messages) where:
            - session_id: The session ID (new or existing)
            - messages: List of message dicts with role and content
        
        Raises:
            Exception: If LLM call or tool execution fails.
        """
        async with self._lock:  # Prevent concurrent access to sessions
            try:
                # Get or create session
                if session_id and session_id in self._sessions:
                    messages = self._sessions[session_id]
                    logger.info(f"Continuing session: {session_id}")
                else:
                    session_id = self.create_session()
                    messages = self._sessions[session_id]
                    # Add system message for new sessions
                    messages.append({"role": "system", "content": SYSTEM_PROMPT})

                # Conversation ID for logging
                self._conversation_id = f"{session_id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                
                logger.info(f"Processing query: {query}")
                user_message = {"role": "user", "content": query}
                messages.append(user_message)

                iteration = 0
                while iteration < settings.max_iterations:
                    iteration += 1
                    response = await self._call_llm(messages)
                    message = response.choices[0].message

                    # the response is a text message
                    if not message.tool_calls:
                        assistant_message = {
                            "role": "assistant",
                            "content": message.content,
                        }
                        messages.append(assistant_message)
                        break

                    # the response is a tool call
                    assistant_message = message.model_dump()
                    messages.append(assistant_message)

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_use_id = tool_call.id
                        
                        logger.info(f"Calling tool {tool_name} with args {tool_args}")
                        
                        try:
                            # Add timeout for tool execution
                            result = await asyncio.wait_for(
                                self.session.call_tool(tool_name, tool_args),
                                timeout=settings.tool_timeout
                            )
                            tool_content = str(result.content)
                            logger.info(f"Tool {tool_name} result: {tool_content[:100]}...")
                        except asyncio.TimeoutError:
                            logger.error(f"Tool {tool_name} timed out after {settings.tool_timeout}s")
                            tool_content = f"Error: Tool '{tool_name}' timed out after {settings.tool_timeout} seconds"
                        except Exception as e:
                            logger.error(f"Tool {tool_name} failed: {e}")
                            tool_content = f"Error: Tool '{tool_name}' failed with error: {str(e)}"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": tool_content,
                        })
                else:
                    # Max iterations reached
                    logger.warning(f"Max iterations ({settings.max_iterations}) reached")
                    messages.append({
                        "role": "assistant",
                        "content": "I apologize, but I've reached the maximum number of steps for this query. Please try breaking down your request into smaller parts.",
                    })

                await self._log_conversation(session_id, messages)
                return session_id, messages

            except Exception as e:
                logger.error(f"Error processing query: {e}")
                raise

    async def process_query_stream(self, query: str, session_id: str | None = None):
        """Process a query with streaming, yielding events for each step.
        
        Yields dictionaries with event types:
        - {"type": "session", "session_id": str}
        - {"type": "tool_call", "tool_name": str, "tool_args": dict}
        - {"type": "tool_result", "tool_name": str, "result": str}
        - {"type": "response", "content": str}
        - {"type": "error", "message": str}
        - {"type": "done", "session_id": str}
        """
        async with self._lock:
            try:
                # Get or create session
                if session_id and session_id in self._sessions:
                    messages = self._sessions[session_id]
                    logger.info(f"Continuing session: {session_id}")
                else:
                    session_id = self.create_session()
                    messages = self._sessions[session_id]
                    messages.append({"role": "system", "content": SYSTEM_PROMPT})

                yield {"type": "session", "session_id": session_id}
                
                self._conversation_id = f"{session_id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                
                logger.info(f"Processing query (streaming): {query}")
                messages.append({"role": "user", "content": query})

                iteration = 0
                while iteration < settings.max_iterations:
                    iteration += 1
                    response = await self._call_llm(messages)
                    message = response.choices[0].message

                    if not message.tool_calls:
                        assistant_message = {
                            "role": "assistant",
                            "content": message.content,
                        }
                        messages.append(assistant_message)
                        yield {"type": "response", "content": message.content}
                        break

                    assistant_message = message.model_dump()
                    messages.append(assistant_message)

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_use_id = tool_call.id
                        
                        yield {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args}
                        
                        try:
                            result = await asyncio.wait_for(
                                self.session.call_tool(tool_name, tool_args),
                                timeout=settings.tool_timeout
                            )
                            tool_content = str(result.content)
                            yield {"type": "tool_result", "tool_name": tool_name, "result": tool_content[:500]}
                        except asyncio.TimeoutError:
                            tool_content = f"Error: Tool '{tool_name}' timed out after {settings.tool_timeout} seconds"
                            yield {"type": "tool_result", "tool_name": tool_name, "result": tool_content}
                        except Exception as e:
                            tool_content = f"Error: Tool '{tool_name}' failed: {str(e)}"
                            yield {"type": "tool_result", "tool_name": tool_name, "result": tool_content}
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": tool_content,
                        })
                else:
                    logger.warning(f"Max iterations ({settings.max_iterations}) reached")
                    max_iter_msg = "I apologize, but I've reached the maximum number of steps for this query."
                    messages.append({"role": "assistant", "content": max_iter_msg})
                    yield {"type": "response", "content": max_iter_msg}

                await self._log_conversation(session_id, messages)
                yield {"type": "done", "session_id": session_id}

            except Exception as e:
                logger.error(f"Error processing query (streaming): {e}")
                yield {"type": "error", "message": str(e)}

    # call llm
    async def _call_llm(self, messages: list):
        """Internal method to call the LLM with exponential backoff retry."""
        last_error = None
        
        for attempt in range(settings.llm_max_retries):
            try:
                logger.info(f"Calling LLM: {settings.llm_model} (attempt {attempt + 1}/{settings.llm_max_retries})")
                return await litellm.acompletion(
                    model=settings.llm_model,
                    temperature=settings.llm_temperature,
                    messages=messages,
                    tools=self.tools,
                )
            except Exception as e:
                last_error = e
                if attempt < settings.llm_max_retries - 1:
                    delay = settings.llm_retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"LLM call failed after {settings.llm_max_retries} attempts: {e}")
        
        raise last_error

    # cleanup
    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()
            raise

    async def _log_conversation(self, session_id: str, messages: list):
        """Save conversation to a JSON file asynchronously."""
        os.makedirs(settings.conversation_log_dir, exist_ok=True)
        filepath = os.path.join(settings.conversation_log_dir, f"conversation_{self._conversation_id}.json")
        
        try:
            async with aiofiles.open(filepath, "w") as f:
                content = json.dumps({"session_id": session_id, "messages": messages}, indent=2, default=str)
                await f.write(content)
        except Exception as e:
            logger.error(f"Error writing conversation: {e}")