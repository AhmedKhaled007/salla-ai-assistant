"""Application service coordinating conversations and agent execution."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from datetime import datetime

import aiofiles

from agent.core import logger, settings
from agent.services.agent_runner import AgentRunner
from agent.services.conversation import ConversationService, exclude_system_messages
from agent.services.mcp_client import MCPClient
from agent.services.prompts import SYSTEM_PROMPT


class QueryProcessor:
    """Coordinate conversation lifecycle around an agent run."""

    def __init__(
        self,
        mcp_client: MCPClient,
    ) -> None:
        self.mcp_client = mcp_client
        self.conversation_service = ConversationService()
        self.agent_runner = AgentRunner()

    async def process_query(
        self,
        query: str,
        conversation_id: str | None = None,
        token: str | None = None,
        user_id: int | None = None,
    ) -> tuple[str, list]:
        """Process a query and return its conversation ID and messages."""
        messages, conversation_id, needs_initialization = (
            await self._prepare_conversation(conversation_id, user_id)
        )
        if needs_initialization:
            await self._generate_title(conversation_id, query)

        messages.append({"role": "user", "content": query})

        async with self.mcp_client.connect(token) as mcp_connection:
            tools = await self.mcp_client.get_openai_tools(mcp_connection)

            async def execute_tool(name, arguments):
                return await self.mcp_client.execute_tool(
                    mcp_connection,
                    name,
                    arguments,
                )

            completed_messages = await self.agent_runner.run(
                messages,
                tools,
                execute_tool,
            )

        await self.conversation_service.save_history(conversation_id, completed_messages)
        await self._log_conversation(conversation_id, completed_messages)

        return conversation_id, exclude_system_messages(completed_messages)

    async def process_query_stream(
        self,
        query: str,
        conversation_id: str | None = None,
        token: str | None = None,
        user_id: int | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Process a query with streaming, yielding public API events."""
        try:
            (
                messages,
                conversation_id,
                needs_initialization,
            ) = await self._prepare_conversation(conversation_id, user_id)

            yield {"type": "conversation", "conversation_id": conversation_id}

            if needs_initialization:
                await self.conversation_service.add_message(
                    conversation_id,
                    messages[0],
                )
                title = await self._generate_title(conversation_id, query)
                if title:
                    yield {"type": "title", "title": title}

            user_message = {"role": "user", "content": query}
            messages.append(user_message)
            await self.conversation_service.add_message(conversation_id, user_message)

            completed_messages = messages
            async with self.mcp_client.connect(token) as mcp_connection:
                tools = await self.mcp_client.get_openai_tools(mcp_connection)

                async def execute_tool(name, arguments):
                    return await self.mcp_client.execute_tool(
                        mcp_connection,
                        name,
                        arguments,
                    )

                async for event in self.agent_runner.stream(
                    messages,
                    tools,
                    execute_tool,
                ):
                    if event["type"] == "message":
                        await self.conversation_service.add_message(
                            conversation_id,
                            event["message"],
                        )
                    elif event["type"] == "complete":
                        completed_messages = event["messages"]
                    else:
                        yield event

            await self._log_conversation(conversation_id, completed_messages)
            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "messages": exclude_system_messages(completed_messages),
            }
        except Exception as error:
            logger.exception("Error in process_query_stream: %s", error)
            yield {"type": "error", "message": str(error)}

    async def _prepare_conversation(
        self,
        conversation_id: str | None,
        user_id: int | None,
    ) -> tuple[list, str, bool]:
        messages = []
        if conversation_id:
            messages = await self.conversation_service.get_history(conversation_id)
        else:
            if user_id is None:
                raise ValueError("user_id is required when creating a conversation")
            conversation_id = await self.conversation_service.create_conversation(
                user_id=user_id
            )

        needs_initialization = not messages
        if needs_initialization:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        return messages, conversation_id, needs_initialization

    async def _generate_title(self, conversation_id: str, query: str):
        try:
            title = await self.conversation_service.generate_title(query)
            await self.conversation_service.update_title(conversation_id, title)
            return title
        except Exception as error:
            logger.warning("Failed to generate conversation title: %s", error)
            return None

    async def _log_conversation(
        self,
        conversation_id: str,
        messages: list,
    ) -> None:
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
            for message in messages:
                if isinstance(message, dict):
                    serializable_messages.append(message)
                else:
                    try:
                        serializable_messages.append(dict(message))
                    except (TypeError, ValueError, AttributeError):
                        serializable_messages.append(str(message))

            async with aiofiles.open(filename, mode="w") as file:
                await file.write(
                    json.dumps(serializable_messages, indent=2, ensure_ascii=False)
                )
        except Exception as error:
            logger.warning("Failed to log conversation: %s", error)
