"""MCP (Model Context Protocol) client for communicating with tool servers.

This module implements the core agent logic:
1. Connects to MCP servers (via HTTP or stdio)
2. Maintains isolated sessions per user token
3. Processes user queries using LLMs (via LiteLLM)
4. Executes tools within the correct session context
"""

from contextlib import AsyncExitStack
import asyncio
import json
import os
import contextvars
import hashlib
from typing import Optional, Any
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


from agent.core import settings, logger
from agent.services.conversation import ConversationService

# Context for multi-tenant token isolation
token_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("mcp_token", default=None)


class MCPClient:
    """Singleton MCP client for communicating with tool servers.

    This client maintains isolated MCP sessions per user/token.
    """

    def __init__(self, transport: str = "http", server_url: Optional[str] = None):
        """Initialize the MCP client.

        Args:
            transport: Transport type - 'stdio' (legacy/single-user) or 'http'
            server_url: URL for HTTP transport
        """
        self.transport = transport
        self.server_url = server_url or settings.mcp_server_url

        # Internal cache for user-specific sessions: {token_hash: (ClientSession, AsyncExitStack)}
        self._sessions: dict[str, tuple[ClientSession, AsyncExitStack]] = {}

        # Cached tool definitions (global)
        self._cached_tools: Optional[list] = None
        self._cached_openai_tools: Optional[list] = None

        # Service for conversation persistence
        self.conversation_service = ConversationService()

    async def _remove_session(self, token: Optional[str] = None):
        """Remove a session from the cache."""
        token = token or token_context.get()
        token_hash = self._get_token_hash(token)
        if token_hash in self._sessions:
            try:
                session, stack = self._sessions.pop(token_hash)
                logger.info(f"Removing session for token hash: {token_hash[:8]}")
                # Add timeout to prevent hanging on cleanup
                try:
                    await asyncio.wait_for(stack.aclose(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout while closing session for {token_hash[:8]}")
                except Exception as e:
                    logger.warning(f"Error closing session for {token_hash[:8]}: {e}")
            except Exception as e:
                logger.error(f"Error removing session: {e}")

    def _get_token_hash(self, token: Optional[str]) -> str:
        """Hash token to use as session key."""
        if not token:
            return "anonymous"
        return hashlib.sha256(token.encode()).hexdigest()

    async def get_session(self, token: Optional[str] = None) -> ClientSession:
        """Get or create an MCP session for the specific token context."""
        token = token or token_context.get()
        token_hash = self._get_token_hash(token)

        if token_hash in self._sessions:
            return self._sessions[token_hash][0]

        logger.info(f"Establishing new MCP session for token hash: {token_hash[:8]}...")

        if self.transport == "http":
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            # Pre-check connectivity
            try:
                async with httpx.AsyncClient() as client:
                    await client.head(self.server_url, timeout=2.0)
            except Exception as e:
                logger.warning(f"MCP server connectivity check failed: {e}")
                # We still try to connect so streamablehttp_client can handle it properly if it was transient

            # Create a dedicated exit stack for this session
            stack = AsyncExitStack()

            try:
                read_stream, write_stream, _ = await stack.enter_async_context(
                    streamablehttp_client(self.server_url, headers=headers)
                )

                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

                await session.initialize()
            except Exception:
                await stack.aclose()
                raise
        else:
            # Create a dedicated exit stack for this session
            stack = AsyncExitStack()

            server_path = settings.server_script_path
            env = os.environ.copy()
            if token:
                env["SALLA_ACCESS_TOKEN"] = token

            server_params = StdioServerParameters(
                command="python" if server_path.endswith('.py') else "node",
                args=[server_path],
                env=env
            )

            try:
                session = await stack.enter_async_context(stdio_client(server_params))
                await session.initialize()
            except Exception:
                await stack.aclose()
                raise

        self._sessions[token_hash] = (session, stack)

        # Ensure tools are loaded into global cache at least once
        # using the first available session
        if self._cached_tools is None:
            await self._load_tools(token, session=session)

        return session

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: dict,
        max_retries: int = 2,
    ) -> str:
        """Execute a tool call using the current context's session."""
        for attempt in range(max_retries + 1):
            try:
                session = await self.get_session()
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, tool_args),
                    timeout=settings.tool_timeout
                )
                logger.info(f"Tool {tool_name} executed successfully, result: {result}")
                # Check for tool execution errors
                if getattr(result, 'isError', False):
                    error_text = "\n".join([c.text for c in result.content if c.type == 'text']
                                           ) if hasattr(result, 'content') else str(result)
                    logger.error(f"Tool {tool_name} execution error: {error_text}")

                if hasattr(result, 'content') and result.content:
                    return "\n".join([c.text for c in result.content if c.type == 'text'])
                return str(result)

            except asyncio.TimeoutError:
                if attempt < max_retries:
                    logger.warning(f"Tool {tool_name} timed out, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    raise asyncio.TimeoutError(f"Tool {tool_name} timed out")
            except Exception as e:
                logger.warning(f"Tool {tool_name} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                await self._remove_session()

                if attempt < max_retries:
                    logger.info("Retrying with new session...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    raise

        raise RuntimeError(f"Tool {tool_name} failed")

    async def ping(self, token: Optional[str] = None) -> bool:
        """Verify the MCP connection for the given token context.

        This will attempt to establish a session if it doesn't exist,
        and send a ping to verify the server is responsive.
        """
        try:
            session = await self.get_session(token)
            await session.send_ping()
            return True
        except Exception as e:
            logger.error(f"MCP Connection check failed: {e}")
            await self._remove_session(token)
            return False

    async def _load_tools(self, token: Optional[str] = None, session: Optional[Any] = None):
        """Load and cache tool definitions."""
        session = session or await self.get_session(token)
        tools_result = await session.list_tools()
        self._cached_tools = tools_result.tools

        self._cached_openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema
                }
            } for t in self._cached_tools
        ]

    async def get_mcp_tools(self, token: Optional[str] = None):
        """Get available tools."""
        if not self._cached_tools:
            await self._load_tools(token)
        return self._cached_tools

    def get_openai_tools(self) -> list:
        """Get cached OpenAI-format tools."""
        if self._cached_openai_tools is None:
            raise RuntimeError("Tools not loaded. Call get_mcp_tools() first.")
        return self._cached_openai_tools

    async def cleanup(self):
        """Clean up all sessions."""
        if not self._sessions:
            return

        logger.info(f"Cleaning up {len(self._sessions)} active sessions...")
        # Create a list of cleanups to run
        cleanups = []
        for token_hash, (session, stack) in list(self._sessions.items()):
            cleanups.append(stack.aclose())

        # Run all cleanups with timeout
        if cleanups:
            try:
                await asyncio.wait_for(asyncio.gather(*cleanups, return_exceptions=True), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout during MCP client cleanup")
            except asyncio.CancelledError:
                logger.warning("MCP client cleanup was cancelled during shutdown")
            except Exception as e:
                logger.error(f"Error during MCP client cleanup: {e}")

        self._sessions.clear()
