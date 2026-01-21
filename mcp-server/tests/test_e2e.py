import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from mcp_server.main import list_products, create_product, list_orders
import json

# Integration/E2E style test mocking the network layer but using real tool entry points


@pytest.mark.asyncio
async def test_e2e_product_lifecycle():
    # Simulate Context with Authorization header
    mock_ctx = MagicMock()
    mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

    # Mock the shared client logic
    with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
        mock_client_instance = AsyncMock()
        mock_get_client.return_value = mock_client_instance

        # 1. List Products logic
        # Mock the build_request call to return something valid
        mock_client_instance.build_request.return_value = Mock()

        # Mock the send responses
        # We need to chain responses for subsequent calls

        mock_resp_list = Mock()
        mock_resp_list.status_code = 200
        mock_resp_list.json.return_value = {"data": [{"id": 1}], "pagination": {}}

        mock_resp_create = Mock()
        mock_resp_create.status_code = 200
        mock_resp_create.json.return_value = {"data": {"id": 123, "name": "E2E Product"}}

        # Configure side effect for send
        mock_client_instance.send.side_effect = [mock_resp_list, mock_resp_create]

        # Test: List Products
        products_json = await list_products(mock_ctx, page=1, per_page=10)
        products = json.loads(products_json)
        assert "data" in products

        # Test: Create Product
        new_product_json = await create_product(mock_ctx, name="E2E Product", price=50.0)
        new_product = json.loads(new_product_json)
        assert new_product["data"]["name"] == "E2E Product"


@pytest.mark.asyncio
async def test_e2e_error_propagation():
    mock_ctx = MagicMock()
    mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

    with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
        mock_client_instance = AsyncMock()
        mock_get_client.return_value = mock_client_instance

        mock_client_instance.build_request.return_value = Mock()

        mock_resp_error = Mock()
        mock_resp_error.status_code = 401
        # json method needs to be callable
        # For error handling in SallaClient, it calls response.json()
        mock_resp_error.json.return_value = {"message": "Unauthorized"}

        mock_client_instance.send.return_value = mock_resp_error

        # Call tool
        result = await list_orders(mock_ctx)

        # Should return formatted error string
        assert "API Error (401): Unauthorized" in result
