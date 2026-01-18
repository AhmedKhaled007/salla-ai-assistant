"""Tests for the Agent Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.agent.mcp_client import MCPClient
from src.agent.main import app


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
# API Endpoint Tests
# ============================================================================

@pytest.fixture
def mock_client():
    """Create a mock MCPClient for testing."""
    mock = MagicMock(spec=MCPClient)
    mock.session = MagicMock()  # Simulate connected state
    mock.list_sessions.return_value = []
    mock._sessions = {}
    return mock


@pytest.fixture
async def async_client(mock_client):
    """Create an async test client."""
    app.state.client = mock_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(async_client, mock_client):
    """Test health check endpoint."""
    mock_client.list_sessions.return_value = ["session1", "session2"]
    
    response = await async_client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mcp_connected"] is True
    assert data["active_sessions"] == 2


@pytest.mark.asyncio
async def test_health_check_degraded(async_client, mock_client):
    """Test health check shows degraded when MCP disconnected."""
    mock_client.session = None
    mock_client.list_sessions.return_value = []
    
    response = await async_client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mcp_connected"] is False


@pytest.mark.asyncio
async def test_process_query(async_client, mock_client):
    """Test query processing endpoint."""
    mock_client.process_query = AsyncMock(return_value=(
        "test-session-id",
        [{"role": "assistant", "content": "Hello!"}]
    ))
    
    response = await async_client.post(
        "/query",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-id"
    assert len(data["messages"]) == 1


@pytest.mark.asyncio
async def test_process_query_with_session(async_client, mock_client):
    """Test query with existing session ID."""
    mock_client.process_query = AsyncMock(return_value=(
        "existing-session",
        [{"role": "assistant", "content": "Continued conversation"}]
    ))
    
    response = await async_client.post(
        "/query",
        json={"query": "Continue", "session_id": "existing-session"}
    )
    
    assert response.status_code == 200
    mock_client.process_query.assert_called_once_with("Continue", "existing-session")


@pytest.mark.asyncio
async def test_create_session(async_client, mock_client):
    """Test session creation endpoint."""
    mock_client.create_session.return_value = "new-session-id"
    
    response = await async_client.post("/sessions")
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "new-session-id"


@pytest.mark.asyncio
async def test_list_sessions(async_client, mock_client):
    """Test listing sessions endpoint."""
    mock_client.list_sessions.return_value = ["session1", "session2"]
    
    response = await async_client.get("/sessions")
    
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == ["session1", "session2"]


@pytest.mark.asyncio
async def test_get_session(async_client, mock_client):
    """Test getting a specific session."""
    mock_client.get_session.return_value = [{"role": "user", "content": "test"}]
    
    response = await async_client.get("/sessions/test-session")
    
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session"
    assert len(data["messages"]) == 1


@pytest.mark.asyncio
async def test_get_session_not_found(async_client, mock_client):
    """Test getting a non-existent session returns 404."""
    mock_client.get_session.return_value = None
    
    response = await async_client.get("/sessions/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(async_client, mock_client):
    """Test deleting a session."""
    mock_client.delete_session.return_value = True
    
    response = await async_client.delete("/sessions/test-session")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_session_not_found(async_client, mock_client):
    """Test deleting a non-existent session returns 404."""
    mock_client.delete_session.return_value = False
    
    response = await async_client.delete("/sessions/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tools(async_client, mock_client):
    """Test getting available tools."""
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.inputSchema = {"type": "object"}
    mock_client.get_mcp_tools = AsyncMock(return_value=[mock_tool])
    
    response = await async_client.get("/tools")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "test_tool"
