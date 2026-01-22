"""Tests for the Agent Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from agent.services import MCPClient
from agent.services.conversation import ConversationService
from agent.main import app
from agent.repositories import (
    InMemoryTokenRepository,
    InMemoryStateRepository,
    InMemoryRateLimitRepository,
    InMemoryConversationRepository,
)


# ============================================================================
# MCPClient Tests
# ============================================================================

@pytest.mark.asyncio
class TestMCPClient:
    """Tests for MCPClient class."""

    async def test_client_initialization(self):
        """Test MCPClient can be initialized with different transports."""
        client = MCPClient(transport="http")
        assert client.transport == "http"

        client_stdio = MCPClient(transport="stdio")
        assert client_stdio.transport == "stdio"

    async def test_ping_returns_false_when_not_connected(self):
        """Test ping returns False when no connection can be established."""
        client = MCPClient()
        # Note: ping(token=None) will fail if no server url or no server running
        with patch.object(MCPClient, 'get_session', side_effect=Exception("Connection failed")):
            assert await client.ping() is False

    async def test_conversation_service_is_initialized(self):
        """Test MCPClient initializes ConversationService."""
        client = MCPClient()
        assert client.conversation_service is not None
        assert isinstance(client.conversation_service, ConversationService)


@pytest.mark.asyncio
class TestConversationService:
    """Tests for ConversationService class."""

    async def test_create_conversation(self):
        """Test conversation creation returns valid UUID."""
        with patch.object(ConversationService, '_conversation_repo') as mock_repo:
            mock_repo.create = AsyncMock()
            service = ConversationService()
            service._conversation_repo = mock_repo

            conversation_id = await service.create_conversation(user_id=1)

            assert conversation_id is not None
            assert len(conversation_id) == 36  # UUID format

    async def test_get_history_returns_messages(self):
        """Test getting conversation history."""
        with patch.object(ConversationService, '_conversation_repo') as mock_repo:
            mock_repo.get = AsyncMock(return_value=[{"role": "user", "content": "test"}])
            service = ConversationService()
            service._conversation_repo = mock_repo

            messages = await service.get_history("test-conversation-id")

            assert messages is not None
            assert len(messages) == 1
            assert messages[0]["role"] == "user"


# ============================================================================
# Repository Tests
# ============================================================================

class TestInMemoryTokenRepository:
    """Tests for InMemoryTokenRepository."""

    @pytest.mark.asyncio
    async def test_store_and_get(self):
        """Test storing and retrieving tokens."""
        repo = InMemoryTokenRepository()
        await repo.store("session1", {"access_token": "token123"}, ttl_seconds=3600)
        result = await repo.get("session1")
        assert result is not None
        assert result["access_token"] == "token123"


# ============================================================================
# API Endpoint Tests
# ============================================================================

@pytest.fixture
def mock_mcp_client():
    """Create a mock MCPClient for testing."""
    mock = MagicMock(spec=MCPClient)
    mock.ping = AsyncMock(return_value=True)
    mock.cleanup = AsyncMock()
    return mock


@pytest.fixture
async def async_client(mock_mcp_client):
    """Create an async test client."""
    app.state.mcp_client = mock_mcp_client
    transport = ASGITransport(app=app)

    with patch("agent.api.routes.query.get_valid_access_token", new_callable=AsyncMock) as m2, \
            patch("agent.api.routes.health.get_valid_access_token", new_callable=AsyncMock) as m3:

        m2.return_value = "test-token"
        m3.return_value = "test-token"

        headers = {"X-Auth-Session-Id": "test-session-id"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            yield client, mock_mcp_client


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health check endpoint."""
    client, mock_mcp = async_client
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mcp_server"] == "connected"


@pytest.mark.asyncio
async def test_process_query(async_client):
    """Test query processing endpoint."""
    client, mock_mcp = async_client
    mock_mcp.process_query = AsyncMock(return_value=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"}
    ])

    response = await client.post(
        "/api/query",
        json={"query": "Hello"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    mock_mcp.process_query.assert_called_once()


@pytest.mark.asyncio
async def test_process_query_with_conversation(async_client):
    """Test query with existing conversation ID."""
    client, mock_mcp = async_client
    mock_mcp.process_query = AsyncMock(return_value=[
        {"role": "assistant", "content": "Continued"}
    ])

    response = await client.post(
        "/api/query",
        json={"query": "Continue", "conversation_id": "existing-id"}
    )

    assert response.status_code == 200
    # Capture the kwargs to verify token was passed
    args, kwargs = mock_mcp.process_query.call_args
    assert args[0] == "Continue"
    assert args[1] == "existing-id"
    assert kwargs["token"] == "test-token"
