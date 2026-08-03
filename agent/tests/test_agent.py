"""Tests for the Agent Service."""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from mcp.types import ListToolsResult, Tool

from agent.services import MCPClient
from agent.services.conversation import ConversationService
from agent.main import app
from agent.repositories import InMemoryTokenRepository


# ============================================================================
# MCPClient Tests
# ============================================================================

@pytest.mark.asyncio
class TestMCPClient:
    """Tests for MCPClient class."""

    async def test_client_initialization(self):
        """Test MCPClient can be initialized with an HTTP server URL."""
        client = MCPClient(server_url="http://mcp.example/mcp")
        assert client.server_url == "http://mcp.example/mcp"

    async def test_probe_returns_false_when_not_connected(self):
        """Test probe reports a failed connection without raising."""
        client = MCPClient()

        @asynccontextmanager
        async def failed_connect(token=None):
            raise ConnectionError("Connection failed")
            yield

        with patch.object(client, "connect", side_effect=failed_connect):
            probe = await client.probe()

        assert probe["connected"] is False
        assert probe["protocol_version"] is None


@pytest.mark.asyncio
class TestConversationService:
    """Tests for ConversationService class."""

    async def test_create_conversation_logic(self):
        """Test conversation creation returns valid UUID."""
        # Use a fresh instance with mocked repo
        service = ConversationService()
        mock_repo = AsyncMock()
        service._conversation_repo = mock_repo
        
        conversation_id = await service.create_conversation(user_id=1)
        
        assert conversation_id is not None
        assert len(conversation_id) == 36

    async def test_get_history_returns_messages(self):
        """Test getting conversation history."""
        service = ConversationService()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = [{"role": "user", "content": "test"}]
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
    mock.probe = AsyncMock(return_value={
        "connected": True,
        "protocol_version": "2026-07-28",
        "server_name": "salla_mcp",
        "tool_count": 12,
    })
    connection = MagicMock()
    connection.list_tools = AsyncMock(return_value=ListToolsResult(tools=[
        Tool(name="salla_list_products", inputSchema={"type": "object"}),
        Tool(name="salla_get_store_info", inputSchema={"type": "object"}),
    ]))

    @asynccontextmanager
    async def connect(token=None):
        yield connection

    mock.connect.side_effect = connect
    return mock


@pytest.fixture
def mock_query_processor():
    """Create a mock QueryProcessor."""
    from agent.services.query_processor import QueryProcessor
    mock = MagicMock(spec=QueryProcessor)
    return mock


@pytest.fixture
async def async_client(mock_mcp_client, mock_query_processor):
    """Create an async test client."""
    app.state.mcp_client = mock_mcp_client
    transport = ASGITransport(app=app)

    # Note: process_query route calls get_query_processor and get_user_id directly, 
    # not via Depends for these specific calls (except auth_session_id).
    # So we must patch them where they are imported in the route module.

    with patch("agent.api.routes.query.get_valid_access_token", new_callable=AsyncMock) as m2, \
            patch("agent.api.routes.health.get_valid_access_token", new_callable=AsyncMock) as m3, \
            patch("agent.api.routes.query.get_query_processor") as mock_get_qp, \
            patch("agent.api.routes.query.get_user_id", new_callable=AsyncMock) as mock_get_uid:

        m2.return_value = "test-token"
        m3.return_value = "test-token"
        
        # Configure get_query_processor to return the mock
        mock_get_qp.return_value = mock_query_processor
        
        # Configure get_user_id
        mock_get_uid.return_value = 1

        headers = {"X-Auth-Session-Id": "test-session-id"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            yield client, mock_query_processor


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health check endpoint."""
    client, _ = async_client
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mcp_server"] == "connected"
    assert data["mcp_protocol_version"] == "2026-07-28"
    assert data["mcp_server_name"] == "salla_mcp"


@pytest.mark.asyncio
async def test_get_tools_uses_token_scoped_connection(async_client, mock_mcp_client):
    client, _ = async_client

    response = await client.get("/tools")

    assert response.status_code == 200
    assert response.json() == {
        "tools": ["salla_list_products", "salla_get_store_info"]
    }
    mock_mcp_client.connect.assert_called_once_with("test-token")


@pytest.mark.asyncio
async def test_process_query(async_client):
    """Test query processing endpoint."""
    client, mock_qp = async_client
    mock_qp.process_query = AsyncMock(return_value=("new-conversation-id", [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"}
    ]))

    response = await client.post(
        "/api/query",
        json={"query": "Hello"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "new-conversation-id"
    assert len(data["messages"]) == 2
    mock_qp.process_query.assert_called_once()


@pytest.mark.asyncio
async def test_process_query_with_conversation(async_client):
    """Test query with existing conversation ID."""
    client, mock_qp = async_client
    mock_qp.process_query = AsyncMock(return_value=("existing-id", [
        {"role": "assistant", "content": "Continued"}
    ]))

    response = await client.post(
        "/api/query",
        json={"query": "Continue", "conversation_id": "existing-id"}
    )

    assert response.status_code == 200
    # Capture the kwargs to verify token was passed
    args, kwargs = mock_qp.process_query.call_args
    assert args[0] == "Continue"
    assert args[1] == "existing-id"
    assert kwargs["token"] == "test-token"
