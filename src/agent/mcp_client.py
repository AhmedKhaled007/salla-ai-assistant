from typing import Optional
from contextlib import AsyncExitStack
import asyncio
import traceback
import json
import os
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
        self.messages = []
        self._lock = asyncio.Lock()  # Serialize concurrent requests

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
    async def process_query(self, query: str):
        async with self._lock:  # Prevent concurrent access to messages
            try:
                # New conversation ID for each query
                self._conversation_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                
                logger.info(f"Processing query: {query}")
                system_message = {"role": "system", "content": SYSTEM_PROMPT}
                user_message = {"role": "user", "content": query}
                self.messages = [system_message, user_message]

                while True:
                    response = await self.call_llm()
                    message = response.choices[0].message

                    # the response is a text message
                    if not message.tool_calls:
                        assistant_message = {
                            "role": "assistant",
                            "content": message.content,
                        }
                        self.messages.append(assistant_message)
                        break

                    # the response is a tool call
                    assistant_message = message.model_dump()
                    self.messages.append(assistant_message)

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
                        
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": tool_content,
                        })

                await self.log_conversation()
                return self.messages

            except Exception as e:
                logger.error(f"Error processing query: {e}")
                raise

    # call llm
    async def call_llm(self):
        try:
            logger.info(f"Calling LLM: {settings.llm_model}")
            return await litellm.acompletion(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                messages=self.messages,
                tools=self.tools,
            )
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise

    # cleanup
    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()
            raise

    async def log_conversation(self):
        """Save conversation to a JSON file."""
        os.makedirs("conversations", exist_ok=True)
        filepath = os.path.join("conversations", f"conversation_{self._conversation_id}.json")
        
        try:
            with open(filepath, "w") as f:
                json.dump(self.messages, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error writing conversation: {e}")