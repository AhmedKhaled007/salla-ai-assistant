"""Tests for the Agent Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from agent.services import MCPClient, MCPClientPool
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
        assert client.session is None  # Not connected yet
        
        client_stdio = MCPClient(transport="stdio")
        assert client_stdio.transport == "stdio"

    async def test_is_connected_returns_false_when_not_connected(self):
        """Test is_connected returns False when no session exists."""
        client = MCPClient()
        assert client.is_connected() is False

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
            
            # Note: create_conversation requires user_id
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

    async def test_get_history_nonexistent(self):
        """Test getting history for non-existent conversation returns empty list."""
        with patch.object(ConversationService, '_conversation_repo') as mock_repo:
            mock_repo.get = AsyncMock(return_value=None)
            service = ConversationService()
            service._conversation_repo = mock_repo
            
            messages = await service.get_history("nonexistent-id")
            
            # Returns empty list when conversation doesn't exist
            assert messages == []

    async def test_save_history(self):
        """Test saving conversation history."""
        with patch.object(ConversationService, '_conversation_repo') as mock_repo:
            mock_repo.store = AsyncMock()
            service = ConversationService()
            service._conversation_repo = mock_repo
            
            await service.save_history("test-id", [{"role": "user", "content": "hello"}])
            
            mock_repo.store.assert_called_once()

    async def test_delete_conversation(self):
        """Test deleting a conversation."""
        with patch.object(ConversationService, '_conversation_repo') as mock_repo:
            mock_repo.delete = AsyncMock(return_value=True)
            service = ConversationService()
            service._conversation_repo = mock_repo
            
            deleted = await service.delete("test-id")
            
            assert deleted is True


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

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting non-existent session returns None."""
        repo = InMemoryTokenRepository()
        
        result = await repo.get("nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting tokens."""
        repo = InMemoryTokenRepository()
        await repo.store("session1", {"access_token": "token123"})
        
        deleted = await repo.delete("session1")
        exists = await repo.exists("session1")
        
        assert deleted is True
        assert exists is False

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test checking if session exists."""
        repo = InMemoryTokenRepository()
        await repo.store("session1", {"access_token": "token123"})
        
        assert await repo.exists("session1") is True
        assert await repo.exists("nonexistent") is False


class TestInMemoryStateRepository:
    """Tests for InMemoryStateRepository."""

    @pytest.mark.asyncio
    async def test_store_and_validate(self):
        """Test storing and validating state."""
        repo = InMemoryStateRepository()
        
        await repo.store("state123", ttl_seconds=600)
        result = await repo.validate_and_consume("state123")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_consumes_state(self):
        """Test that validation consumes the state."""
        repo = InMemoryStateRepository()
        await repo.store("state123")
        
        # First validation should succeed
        result1 = await repo.validate_and_consume("state123")
        # Second should fail (already consumed)
        result2 = await repo.validate_and_consume("state123")
        
        assert result1 is True
        assert result2 is False

    @pytest.mark.asyncio
    async def test_validate_nonexistent(self):
        """Test validating non-existent state returns False."""
        repo = InMemoryStateRepository()
        
        result = await repo.validate_and_consume("nonexistent")
        
        assert result is False


class TestInMemoryRateLimitRepository:
    """Tests for InMemoryRateLimitRepository."""

    @pytest.mark.asyncio
    async def test_under_limit(self):
        """Test requests under limit are allowed."""
        repo = InMemoryRateLimitRepository()
        
        # First request should be allowed
        allowed = await repo.check_and_increment("client1", limit=5, window_seconds=60)
        
        assert allowed is True

    @pytest.mark.asyncio
    async def test_at_limit(self):
        """Test requests at limit are rejected."""
        repo = InMemoryRateLimitRepository()
        
        # Make 5 requests
        for _ in range(5):
            await repo.check_and_increment("client1", limit=5, window_seconds=60)
        
        # 6th request should be rejected
        allowed = await repo.check_and_increment("client1", limit=5, window_seconds=60)
        
        assert allowed is False

    @pytest.mark.asyncio
    async def test_get_remaining(self):
        """Test getting remaining requests."""
        repo = InMemoryRateLimitRepository()
        
        # Make 3 requests
        for _ in range(3):
            await repo.check_and_increment("client1", limit=5, window_seconds=60)
        
        remaining = await repo.get_remaining("client1", limit=5, window_seconds=60)
        
        assert remaining == 2


# ============================================================================
# API Endpoint Tests
# ============================================================================

@pytest.fixture
def mock_client_pool():
    """Create a mock MCPClientPool for testing."""
    mock = MagicMock(spec=MCPClientPool)
    mock.is_connected = MagicMock(return_value=True)
    mock.pool_size = MagicMock(return_value=0)
    mock.active_clients = MagicMock(return_value=0)
    mock.ping = AsyncMock(return_value=True)
    
    # Create a mock client that the pool returns
    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = MagicMock()
    mock_client.list_conversations = AsyncMock(return_value=[])
    mock_client._conversations = {}
    
    mock.get_client = AsyncMock(return_value=mock_client)
    mock.release_client = AsyncMock()
    
    return mock, mock_client


@pytest.fixture
async def async_client(mock_client_pool):
    """Create an async test client."""
    mock_pool, mock_client = mock_client_pool
    app.state.pool = mock_pool
    transport = ASGITransport(app=app)
    
    # Mock get_valid_access_token in all routes provided it's used there
    with patch("src.agent.api.routes.session.get_valid_access_token", new_callable=AsyncMock) as m1, \
         patch("src.agent.api.routes.query.get_valid_access_token", new_callable=AsyncMock) as m2, \
         patch("src.agent.api.routes.health.get_valid_access_token", new_callable=AsyncMock) as m3:
        
        m1.return_value = "test-token"
        m2.return_value = "test-token"
        m3.return_value = "test-token"
        
        headers = {"X-Auth-Session-Id": "test-session-id"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            yield client, mock_pool, mock_client


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health check endpoint."""
    client, mock_pool, mock_client = async_client
    
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mcp_server"] == "connected"


@pytest.mark.asyncio
async def test_health_check_degraded(async_client):
    """Test health check shows degraded when MCP disconnected."""
    client, mock_pool, mock_client = async_client
    mock_pool.ping = AsyncMock(return_value=False)
    
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mcp_server"] == "disconnected"


@pytest.mark.asyncio
async def test_process_query(async_client):
    """Test query processing endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.process_query = AsyncMock(return_value=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"}
    ])
    
    response = await client.post(
        "/api/query",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("messages") is not None
    assert len(data["messages"]) == 2


@pytest.mark.asyncio
async def test_process_query_with_conversation(async_client):
    """Test query with existing conversation ID."""
    client, mock_pool, mock_client = async_client
    mock_client.process_query = AsyncMock(return_value=[
        {"role": "assistant", "content": "Continued conversation"}
    ])
    
    response = await client.post(
        "/api/query",
        json={"query": "Continue", "conversation_id": "existing-conversation"}
    )
    
    assert response.status_code == 200
    mock_client.process_query.assert_called_once_with("Continue", "existing-conversation")


@pytest.mark.asyncio
async def test_create_conversation(async_client):
    """Test conversation creation endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.create_conversation = AsyncMock(return_value="new-conversation-id")
    
    response = await client.post("/api/conversations")
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "new-conversation-id"


@pytest.mark.asyncio
async def test_list_conversations(async_client):
    """Test listing conversations endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.list_conversations = AsyncMock(return_value=["conversation1", "conversation2"])
    
    response = await client.get("/api/conversations")
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversations"] == ["conversation1", "conversation2"]


@pytest.mark.asyncio
async def test_get_conversation(async_client):
    """Test getting a specific conversation."""
    client, mock_pool, mock_client = async_client
    mock_client.get_conversation = AsyncMock(return_value=[{"role": "user", "content": "test"}])
    
    response = await client.get("/api/conversations/test-conversation")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 1


@pytest.mark.asyncio
async def test_get_conversation_not_found(async_client):
    """Test getting a non-existent conversation returns 404."""
    client, mock_pool, mock_client = async_client
    mock_client.get_conversation = AsyncMock(return_value=None)
    
    response = await client.get("/api/conversations/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(async_client):
    """Test deleting a conversation."""
    client, mock_pool, mock_client = async_client
    mock_client.delete_conversation = AsyncMock(return_value=True)
    
    response = await client.delete("/api/conversations/test-conversation")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_conversation_not_found(async_client):
    """Test deleting a non-existent conversation returns 404."""
    client, mock_pool, mock_client = async_client
    mock_client.delete_conversation = AsyncMock(return_value=False)
    
    response = await client.delete("/api/conversations/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tools(async_client):
    """Test getting available tools."""
    client, mock_pool, mock_client = async_client
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.inputSchema = {"type": "object"}
    mock_client.get_mcp_tools = AsyncMock(return_value=[mock_tool])
    
    response = await client.get("/health/tools")  # Correct path is /health/tools ? NO, it is /tools or /health/tools
    # In health.py, router is included in api/__init__ without prefix, but tags=Health.
    # Wait, api_router includes health.router.
    # health.router has @router.get("/tools").
    # api_router is included in main.py.
    # So path is /tools.
    
    response = await client.get("/tools") # Or /health/tools if I messed up.
    # api_router.include_router(health.router, tags=["Health"]) -> No prefix.
    # main.py includes api_router.
    # So path is /tools.
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0] == "test_tool"
