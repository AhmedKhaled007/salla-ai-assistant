import pytest
from unittest.mock import Mock, AsyncMock, patch
from mcp_server.main import list_products, create_product
from mcp_server.salla_client import SallaClient


@pytest.fixture
def mock_context():
    ctx = Mock()
    ctx.request_context.request.headers.get.return_value = "Bearer test-token"
    return ctx


@pytest.mark.asyncio
async def test_list_products_success(mock_context):
    mock_data = {"data": [{"id": 1, "name": "Product 1"}]}

    with patch("mcp_server.main.SallaClient") as MockClient:
        instance = MockClient.return_value
        instance.get = AsyncMock(return_value=mock_data)

        result = await list_products(mock_context, page=1, per_page=10)

        assert "Product 1" in result
        instance.get.assert_called_with("/products", params={"page": 1, "per_page": 10})


@pytest.mark.asyncio
async def test_list_products_invalid_input(mock_context):
    # Should result in error message, not default client call
    result = await list_products(mock_context, page=0)
    assert "Error: page must be greater than 0" in result


@pytest.mark.asyncio
async def test_create_product(mock_context):
    mock_data = {"data": {"id": 1, "name": "New Product"}}

    with patch("mcp_server.main.SallaClient") as MockClient:
        instance = MockClient.return_value
        instance.post = AsyncMock(return_value=mock_data)

        result = await create_product(mock_context, name="New Product", price=100)

        assert "New Product" in result
        instance.post.assert_called_once()
