from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.services.query_processor import QueryProcessor


@pytest.mark.asyncio
async def test_process_query_creates_and_persists_conversation_when_id_is_missing():
    mcp_client = MagicMock()
    mcp_client.ping = AsyncMock()
    mcp_client.get_openai_tools.return_value = []

    processor = QueryProcessor(mcp_client)
    processor.conversation_service = MagicMock()
    processor.conversation_service.create_conversation = AsyncMock(
        return_value="new-conversation-id"
    )
    processor.conversation_service.save_history = AsyncMock()
    processor._log_conversation = AsyncMock()

    llm_response = MagicMock()
    llm_response.choices[0].message.tool_calls = None
    llm_response.choices[0].message.content = "Hello!"

    with patch("agent.services.query_processor.call_llm", new=AsyncMock(return_value=llm_response)):
        conversation_id, messages = await processor.process_query("Hello", user_id=1)

    assert conversation_id == "new-conversation-id"
    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"},
    ]
    processor.conversation_service.create_conversation.assert_awaited_once_with(user_id=1)
    processor.conversation_service.save_history.assert_awaited_once()
    saved_conversation_id, saved_messages = processor.conversation_service.save_history.await_args.args
    assert saved_conversation_id == "new-conversation-id"
    assert saved_messages[0]["role"] == "system"
