"""Tests for the Agent Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.agent.mcp_client import MCPClient
from src.agent.client_pool import MCPClientPool
from src.agent.main import app
from src.agent.repositories import (
    InMemoryTokenRepository,
    InMemoryStateRepository,
    InMemoryRateLimitRepository,
    InMemoryConversationRepository,
)


# ============================================================================
# MCPClient Tests
# ============================================================================

class TestMCPClient:
    """Tests for MCPClient class."""

    def test_create_session(self):
        """Test session creation returns valid UUID."""
        client = MCPClient()
        session_id = client.create_session()
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert session_id in client._sessions
        assert client._sessions[session_id] == []

    def test_get_session_existing(self):
        """Test getting an existing session."""
        client = MCPClient()
        session_id = client.create_session()
        client._sessions[session_id].append({"role": "test"})
        
        messages = client.get_session(session_id)
        
        assert messages is not None
        assert len(messages) == 1
        assert messages[0]["role"] == "test"

    def test_get_session_nonexistent(self):
        """Test getting a non-existent session returns None."""
        client = MCPClient()
        
        messages = client.get_session("nonexistent-id")
        
        assert messages is None

    def test_delete_session_existing(self):
        """Test deleting an existing session."""
        client = MCPClient()
        session_id = client.create_session()
        
        deleted = client.delete_session(session_id)
        
        assert deleted is True
        assert session_id not in client._sessions

    def test_delete_session_nonexistent(self):
        """Test deleting a non-existent session returns False."""
        client = MCPClient()
        
        deleted = client.delete_session("nonexistent-id")
        
        assert deleted is False

    def test_list_sessions(self):
        """Test listing all sessions."""
        client = MCPClient()
        id1 = client.create_session()
        id2 = client.create_session()
        
        sessions = client.list_sessions()
        
        assert len(sessions) == 2
        assert id1 in sessions
        assert id2 in sessions


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
    mock.is_connected = True
    mock.pool_size = 0
    mock.active_clients = 0
    mock.ping = AsyncMock(return_value=True)
    
    # Create a mock client that the pool returns
    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = MagicMock()
    mock_client.list_sessions = MagicMock(return_value=[])
    mock_client._sessions = {}
    
    mock.get_client = AsyncMock(return_value=mock_client)
    mock.release_client = AsyncMock()
    
    return mock, mock_client


@pytest.fixture
async def async_client(mock_client_pool):
    """Create an async test client."""
    mock_pool, mock_client = mock_client_pool
    app.state.client_pool = mock_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_pool, mock_client


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health check endpoint."""
    client, mock_pool, mock_client = async_client
    
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mcp_connected"] is True


@pytest.mark.asyncio
async def test_health_check_degraded(async_client):
    """Test health check shows degraded when MCP disconnected."""
    client, mock_pool, mock_client = async_client
    mock_pool.ping = AsyncMock(return_value=False)
    mock_pool.is_connected = False
    
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mcp_connected"] is False


@pytest.mark.asyncio
async def test_process_query(async_client):
    """Test query processing endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.process_query = AsyncMock(return_value=(
        "test-session-id",
        [{"role": "assistant", "content": "Hello!"}]
    ))
    
    response = await client.post(
        "/query",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-id"
    assert len(data["messages"]) == 1


@pytest.mark.asyncio
async def test_process_query_with_session(async_client):
    """Test query with existing session ID."""
    client, mock_pool, mock_client = async_client
    mock_client.process_query = AsyncMock(return_value=(
        "existing-session",
        [{"role": "assistant", "content": "Continued conversation"}]
    ))
    
    response = await client.post(
        "/query",
        json={"query": "Continue", "session_id": "existing-session"}
    )
    
    assert response.status_code == 200
    mock_client.process_query.assert_called_once_with("Continue", "existing-session")


@pytest.mark.asyncio
async def test_create_session(async_client):
    """Test session creation endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.create_session = MagicMock(return_value="new-session-id")
    
    response = await client.post("/sessions")
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "new-session-id"


@pytest.mark.asyncio
async def test_list_sessions(async_client):
    """Test listing sessions endpoint."""
    client, mock_pool, mock_client = async_client
    mock_client.list_sessions = MagicMock(return_value=["session1", "session2"])
    
    response = await client.get("/sessions")
    
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == ["session1", "session2"]


@pytest.mark.asyncio
async def test_get_session(async_client):
    """Test getting a specific session."""
    client, mock_pool, mock_client = async_client
    mock_client.get_session = MagicMock(return_value=[{"role": "user", "content": "test"}])
    
    response = await client.get("/sessions/test-session")
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session"
    assert len(data["messages"]) == 1


@pytest.mark.asyncio
async def test_get_session_not_found(async_client):
    """Test getting a non-existent session returns 404."""
    client, mock_pool, mock_client = async_client
    mock_client.get_session = MagicMock(return_value=None)
    
    response = await client.get("/sessions/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(async_client):
    """Test deleting a session."""
    client, mock_pool, mock_client = async_client
    mock_client.delete_session = MagicMock(return_value=True)
    
    response = await client.delete("/sessions/test-session")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_session_not_found(async_client):
    """Test deleting a non-existent session returns 404."""
    client, mock_pool, mock_client = async_client
    mock_client.delete_session = MagicMock(return_value=False)
    
    response = await client.delete("/sessions/nonexistent")
    
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
    
    response = await client.get("/tools")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "test_tool"
