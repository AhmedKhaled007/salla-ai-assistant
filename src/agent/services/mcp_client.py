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

import aiofiles

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
import litellm

from ..core import settings, logger
from ..core import get_conversation_repository
from .prompts import SYSTEM_PROMPT


class MCPClient:
    """MCP (Model Context Protocol) client for communicating with tool servers.
    
    This client connects to an MCP server via stdio and provides methods for:
    - Processing user queries using an LLM with tool access
    - Maintaining conversation history
    - Executing tools on the MCP server
    """

    def __init__(self, transport: str = "stdio", server_url: Optional[str] = None):
        """Initialize the MCP client.
        
        Args:
            transport: Transport type - 'stdio' or 'sse'
            server_url: URL for SSE transport (e.g., 'http://localhost:8001/sse')
        """
        # Session state
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Configuration
        self.transport = transport
        self.server_url = server_url or settings.mcp_server_url
        
        # Salla Access Token (for authentication context)
        self._access_token: Optional[str] = None
        
        # Repositories
        self._conversation_repo = get_conversation_repository()

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

    async def create_session(self) -> str:
        """Create a new conversation session and return its ID."""
        session_id = str(uuid.uuid4())
        # We don't need to persist empty sessions, but we could
        logger.info(f"Created new session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[list]:
        """Get messages for a session. Returns None if session doesn't exist."""
        repo = self._conversation_repo
        return await repo.get(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        repo = self._conversation_repo
        # We might also want to delete log files if we were strictly cleaning up
        return await repo.delete(session_id)

    async def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        repo = self._conversation_repo
        return await repo.list_sessions()
        
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
        else: # stdio
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
        """Load available tools from MCP server."""
        if not self.session:
             return
             
        try:
             # Just initialize connection/handshake
             await self.session.initialize()
             
             # Verify tools can be listed
             tools = await self.session.list_tools()
             tool_names = [t.name for t in tools.tools]
             logger.debug(f"Loaded tools: {tool_names}")
             
        except Exception as e:
             logger.error(f"Failed to load tools: {e}")
             raise

    async def get_mcp_tools(self):
        """Get the list of available tools from the MCP server.
        
        Returns:
            List of Tool objects from the MCP server.
        
        Raises:
            Exception: If retrieving tools fails.
        """
        await self.ensure_connected()
        result = await self.session.list_tools()
        return result.tools

    async def process_query(self, query: str, session_id: str | None = None) -> list:
        """Process a user query using the LLM with tool access.
        
        This method sends the query to the LLM, handles any tool calls,
        and returns the complete conversation. If a session_id is provided,
        it uses the existing conversation context.
        
        Args:
            query: The user's query string.
            session_id: Optional session ID to continue a conversation.
            
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
        if session_id:
             stored_messages = await self.get_session(session_id)
             if stored_messages:
                 messages = stored_messages
        
        if not messages:
             # Basic system prompt if no history
             messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add user query
        messages.append({"role": "user", "content": query})

        # Get available tools
        available_tools = await self.session.list_tools()
        
        # Convert MCP tools to OpenAI tool format
        openai_tools = []
        for tool in available_tools.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })

        # Process with tool loop
        iteration_count = 0
        final_response = None
        
        while iteration_count < settings.max_iterations:
            try:
                # Call LLM
                response = await self._call_llm(messages, tools=openai_tools)
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
                            
                            # Execute on MCP server
                            result = await self.session.call_tool(tool_name, tool_args)
                            
                            # Format result text
                            tool_output = ""
                            if hasattr(result, 'content') and result.content:
                                 tool_output = "\n".join([c.text for c in result.content if c.type == 'text'])
                            else:
                                 tool_output = str(result)
                                 
                            # Add result to history
                            messages.append({
                                "role": "tool",
                                "name": tool_name,
                                "tool_call_id": tool_call_id,
                                "content": tool_output
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
        if session_id:
             repo = self._conversation_repo
             await repo.store(session_id, messages)
             
             # Also log to file system for debugging
             await self._log_conversation(session_id, messages)

        # Filter out system messages before returning to client
        return [msg for msg in messages if msg.get("role") != "system"]

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
        await self.ensure_connected()
        
        # Load or initialize conversation
        messages = []
        if session_id:
            logger.info(f"Loading session {session_id}")
            stored_messages = await self.get_session(session_id)
            if stored_messages:
                logger.info(f"Found session message {stored_messages}")
                messages = stored_messages
        else:
            session_id = await self.create_session()
             
        yield {"type": "session", "session_id": session_id}
        
        if not messages:
             messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        messages.append({"role": "user", "content": query})

        # Get tools
        available_tools = await self.session.list_tools()
        openai_tools = []
        for tool in available_tools.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })

        iteration_count = 0
        
        while iteration_count < settings.max_iterations:
            try:
                # Call LLM with streaming
                response = await self._call_llm(messages, tools=openai_tools, stream=True)
                
                current_content = ""
                tool_calls_buffer = {} # index -> data
                
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
                            
                            # Execute on MCP server
                            result = await self.session.call_tool(tool_name, tool_args)
                            
                            # Format result text
                            tool_output = ""
                            if hasattr(result, 'content') and result.content:
                                 tool_output = "\n".join([c.text for c in result.content if c.type == 'text'])
                            else:
                                 tool_output = str(result)
                                 
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
        repo = self._conversation_repo
        await repo.store(session_id, messages)
        await self._log_conversation(session_id, messages)
        
        # Filter out system messages from final messages list
        filtered_messages = [msg for msg in messages if msg.get("role") != "system"]
        yield {"type": "done", "session_id": session_id, "messages": filtered_messages}

    async def _call_llm(self, messages: list, tools: list = None, stream: bool = False):
        """Internal method to call the LLM with exponential backoff retry."""
        retry_delay = settings.llm_retry_delay
        
        for attempt in range(settings.llm_max_retries):
            try:
                # Prepare args
                kwargs = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": settings.llm_temperature,
                }
                
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                    
                if settings.llm_max_tokens:
                    kwargs["max_tokens"] = settings.llm_max_tokens
                    
                if stream:
                    kwargs["stream"] = True
                response = await litellm.acompletion(**kwargs)
                if stream:
                    return response
                
            except Exception as e:
                if attempt == settings.llm_max_retries - 1:
                    logger.error(f"LLM call failed after {settings.llm_max_retries} attempts: {e}")
                    raise
                
                logger.warning(f"LLM call failed (attempt {attempt+1}), retrying in {retry_delay}s: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.exit_stack.aclose()
            self.session = None

    async def _log_conversation(self, session_id: str, messages: list):
        """Save conversation to a JSON file asynchronously."""
        try:
            log_dir = settings.conversation_log_dir
            os.makedirs(log_dir, exist_ok=True)
            
            # Format filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{log_dir}/{session_id}_{timestamp}.json"
            
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
                    except:
                        serializable_messages.append(str(msg))

            async with aiofiles.open(filename, mode='w') as f:
                await f.write(json.dumps(serializable_messages, indent=2, ensure_ascii=False))
                
        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")

