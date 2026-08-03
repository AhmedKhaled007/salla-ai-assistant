"""Shared pytest fixtures for Salla MCP Server tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
import httpx

from mcp_server.salla_client import SallaClient, close_shared_client


# =============================================================================
# CONTEXT FIXTURES
# =============================================================================

@pytest.fixture
def mock_context():
    """Create a mock MCP Context with authorization header."""
    ctx = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.request = MagicMock()
    ctx.request_context.request.headers = {"Authorization": "Bearer test_token_123"}
    return ctx


@pytest.fixture
def mock_context_no_auth():
    """Create a mock MCP Context without authorization header."""
    ctx = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.request = MagicMock()
    ctx.request_context.request.headers = {}
    return ctx


# =============================================================================
# CLIENT FIXTURES
# =============================================================================

@pytest.fixture
async def cleanup_shared_client():
    """Cleanup shared client after tests."""
    yield
    await close_shared_client()


@pytest.fixture
def mock_salla_client():
    """Create a mock SallaClient with all HTTP methods mocked."""
    client = AsyncMock(spec=SallaClient)
    client.get = AsyncMock(return_value={"status": 200, "data": []})
    client.post = AsyncMock(return_value={"status": 200, "data": {}})
    client.put = AsyncMock(return_value={"status": 200, "data": {}})
    client.delete = AsyncMock(return_value={"status": 200, "data": {}})
    return client


@pytest.fixture
def mock_httpx_response():
    """Factory fixture to create mock httpx responses."""
    def _create_response(status_code: int, json_data: dict):
        response = Mock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = json_data
        response.text = str(json_data)
        return response
    return _create_response


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_product():
    """Sample product data from API response."""
    return {
        "id": 12345,
        "name": "Test Product",
        "price": {"amount": 99.99, "currency": "SAR"},
        "quantity": 100,
        "sku": "TEST-SKU-001",
        "status": "sale",
        "type": "product",
        "images": [{"url": "https://example.com/image.jpg"}],
    }


@pytest.fixture
def sample_order():
    """Sample order data from API response."""
    return {
        "id": 67890,
        "reference_id": "ORD-2024-001",
        "status": {"id": 1, "name": "pending", "slug": "pending"},
        "customer": {"id": 111, "name": "Test Customer"},
        "items": [{"product_id": 12345, "quantity": 2, "price": 99.99}],
        "total": {"amount": 199.98, "currency": "SAR"},
    }


@pytest.fixture
def sample_customer():
    """Sample customer data from API response."""
    return {
        "id": 111,
        "first_name": "Ahmed",
        "last_name": "Khaled",
        "email": "ahmed@example.com",
        "mobile": "500000000",
        "mobile_code": "+966",
    }


@pytest.fixture
def sample_pagination():
    """Sample pagination metadata."""
    return {
        "count": 10,
        "total": 100,
        "perPage": 10,
        "currentPage": 1,
        "totalPages": 10,
    }
