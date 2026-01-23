
import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp_server.main import create_customer, list_products, SallaClient
from mcp.server.fastmcp import Context

# Mock Context


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.request_context = MagicMock()
    ctx.request_context.request = MagicMock()
    ctx.request_context.request.headers = {"Authorization": "Bearer test_token"}
    return ctx

# Mock SallaClient


@pytest.fixture
def mock_client(monkeypatch):
    client_mock = AsyncMock(spec=SallaClient)
    client_mock.post = AsyncMock(return_value={"status": 200, "data": {}})
    client_mock.get = AsyncMock(return_value={"status": 200, "data": []})

    # Patch the get_salla_client function or SallaClient constructor if needed
    # Since get_salla_client instantiates SallaClient, we might need to patch SallaClient class
    class MockSallaClient:
        def __init__(self, access_token):
            self.access_token = access_token
            self.post = client_mock.post
            self.get = client_mock.get
            self.put = AsyncMock(return_value={"status": 200, "data": {}})

    monkeypatch.setattr("mcp_server.main.SallaClient", MockSallaClient)
    return client_mock


@pytest.mark.asyncio
async def test_create_customer_payload(mock_context, mock_client):
    # Test with SA country code (should map to 966)
    await create_customer(
        mock_context,
        first_name="Ahmed",
        mobile="500000000",
        country_code="SA"
    )

    # Verify the payload passed to client.post
    mock_client.post.assert_called_with(
        "/customers",
        data={
            "first_name": "Ahmed",
            "mobile": "500000000",
            "mobile_code": "966"  # Expecting mapped code
        }
    )


@pytest.mark.asyncio
async def test_create_customer_numeric_code(mock_context, mock_client):
    # Test with numeric code directly
    await create_customer(
        mock_context,
        first_name="Ali",
        mobile="500000000",
        country_code="971"
    )

    mock_client.post.assert_called_with(
        "/customers",
        data={
            "first_name": "Ali",
            "mobile": "500000000",
            "mobile_code": "971"
        }
    )


@pytest.mark.asyncio
async def test_list_products_validation(mock_context, mock_client):
    # Test with valid status
    await list_products(mock_context, status="sale")
    mock_client.get.assert_called()

    # Test with invalid status (should return error string)
    result = await list_products(mock_context, status="invalid_status")
    assert "Error: Invalid status" in result
