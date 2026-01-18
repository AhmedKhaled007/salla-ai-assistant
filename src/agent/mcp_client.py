from typing import Optional
from contextlib import AsyncExitStack
import asyncio
import traceback
import json
import os
import uuid
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import litellm

from .utils import settings, logger
from .prompts import SYSTEM_PROMPT



class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools = []
        self._sessions: dict[str, list] = {}  # session_id -> messages
        self._lock = asyncio.Lock()  # Serialize concurrent requests

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

    # connect to the MCP server
    async def connect_to_server(self, server_script_path: str):
        try:
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

    # get mcp tool list
    async def get_mcp_tools(self):
        try:
            response = await self.session.list_tools()
            return response.tools
        except Exception as e:
            logger.error(f"Error getting MCP tools: {e}")
            raise

    # process query
    async def process_query(self, query: str, session_id: str | None = None):
        """Process a query, optionally continuing an existing session.
        
        Args:
            query: The user's query
            session_id: Optional session ID. If None, creates a new session.
                       If provided, continues the existing conversation.
        
        Returns:
            Tuple of (session_id, messages)
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
                            result = await self.session.call_tool(tool_name, tool_args)
                            tool_content = str(result.content)
                            logger.info(f"Tool {tool_name} result: {tool_content[:100]}...")
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
        """Save conversation to a JSON file."""
        os.makedirs("conversations", exist_ok=True)
        filepath = os.path.join("conversations", f"conversation_{self._conversation_id}.json")
        
        try:
            with open(filepath, "w") as f:
                json.dump({"session_id": session_id, "messages": messages}, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error writing conversation: {e}")