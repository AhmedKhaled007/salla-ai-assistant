"""End-to-end integration tests for Salla MCP Server."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock

from mcp_server.tools import (
    salla_list_products,
    salla_create_product,
    salla_get_product,
    salla_list_orders,
    salla_create_order,
    salla_list_customers,
    salla_create_customer,
    salla_get_store_info,
)
from mcp_server.models import (
    ListProductsInput,
    CreateProductInput,
    GetProductInput,
    ListOrdersInput,
    CreateOrderInput,
    ListCustomersInput,
    CreateCustomerInput,
    OrderProduct,
    ProductType,
)


class TestProductWorkflow:
    """End-to-end tests for product workflows."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_product(self):
        """Test complete product creation and retrieval workflow."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            # Create product response
            create_response = Mock()
            create_response.status_code = 201
            create_response.json.return_value = {
                "data": {"id": 12345, "name": "New Product", "price": 99.99}
            }

            # Get product response
            get_response = Mock()
            get_response.status_code = 200
            get_response.json.return_value = {
                "data": {"id": 12345, "name": "New Product", "price": 99.99, "quantity": 100}
            }

            mock_client_instance.send.side_effect = [create_response, get_response]

            # Step 1: Create product
            create_params = CreateProductInput(
                name="New Product",
                price=99.99,
                product_type=ProductType.PRODUCT
            )
            create_result = await salla_create_product(create_params, mock_ctx)
            assert create_result["data"]["id"] == 12345

            # Step 2: Retrieve product
            get_params = GetProductInput(product_id=12345)
            get_result = await salla_get_product(get_params, mock_ctx)
            assert get_result["data"]["name"] == "New Product"

    @pytest.mark.asyncio
    async def test_list_filter_products_workflow(self):
        """Test listing and filtering products."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            # First list - all products
            list_all_response = Mock()
            list_all_response.status_code = 200
            list_all_response.json.return_value = {
                "data": [
                    {"id": 1, "name": "Product A", "status": "sale"},
                    {"id": 2, "name": "Product B", "status": "hidden"},
                    {"id": 3, "name": "Product C", "status": "sale"},
                ],
                "pagination": {"total": 3}
            }

            # Second list - filtered
            list_filtered_response = Mock()
            list_filtered_response.status_code = 200
            list_filtered_response.json.return_value = {
                "data": [
                    {"id": 1, "name": "Product A", "status": "sale"},
                    {"id": 3, "name": "Product C", "status": "sale"},
                ],
                "pagination": {"total": 2}
            }

            mock_client_instance.send.side_effect = [list_all_response, list_filtered_response]

            # Step 1: List all products
            all_products = await salla_list_products(ListProductsInput(), mock_ctx)
            assert len(all_products["data"]) == 3

            # Step 2: List filtered products
            filtered = await salla_list_products(
                ListProductsInput(status="sale"),
                mock_ctx
            )
            assert len(filtered["data"]) == 2


class TestOrderWorkflow:
    """End-to-end tests for order workflows."""

    @pytest.mark.asyncio
    async def test_complete_order_workflow(self):
        """Test complete order creation workflow."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            # List customers response
            customers_response = Mock()
            customers_response.status_code = 200
            customers_response.json.return_value = {
                "data": [{"id": 111, "first_name": "Ahmed"}]
            }

            # List products response
            products_response = Mock()
            products_response.status_code = 200
            products_response.json.return_value = {
                "data": [{"id": 12345, "name": "Product A", "price": 50}]
            }

            # Create order response
            order_response = Mock()
            order_response.status_code = 201
            order_response.json.return_value = {
                "data": {
                    "id": 67890,
                    "status": "pending",
                    "total": 100.00
                }
            }

            mock_client_instance.send.side_effect = [
                customers_response,
                products_response,
                order_response
            ]

            # Step 1: Get customer
            customers = await salla_list_customers(ListCustomersInput(), mock_ctx)
            customer_id = customers["data"][0]["id"]

            # Step 2: Get products
            products = await salla_list_products(ListProductsInput(), mock_ctx)
            product_id = products["data"][0]["id"]

            # Step 3: Create order
            order_params = CreateOrderInput(
                customer_id=customer_id,
                products=[OrderProduct(identifier=str(product_id), quantity=2)]
            )
            order_result = await salla_create_order(order_params, mock_ctx)
            
            assert order_result["data"]["id"] == 67890
            assert order_result["data"]["total"] == 100.00


class TestCustomerWorkflow:
    """End-to-end tests for customer workflows."""

    @pytest.mark.asyncio
    async def test_create_and_list_customer(self):
        """Test customer creation and listing."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            # Create customer response
            create_response = Mock()
            create_response.status_code = 201
            create_response.json.return_value = {
                "data": {
                    "id": 222,
                    "first_name": "New",
                    "last_name": "Customer"
                }
            }

            # List customers response
            list_response = Mock()
            list_response.status_code = 200
            list_response.json.return_value = {
                "data": [
                    {"id": 222, "first_name": "New", "last_name": "Customer"}
                ]
            }

            mock_client_instance.send.side_effect = [create_response, list_response]

            # Step 1: Create customer
            create_params = CreateCustomerInput(
                first_name="New",
                last_name="Customer",
                mobile="500000000",
                mobile_code_country="+966"
            )
            create_result = await salla_create_customer(create_params, mock_ctx)
            assert create_result["data"]["id"] == 222

            # Step 2: List to verify
            list_result = await salla_list_customers(ListCustomersInput(), mock_ctx)
            assert any(c["id"] == 222 for c in list_result["data"])


class TestErrorHandling:
    """End-to-end tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_api_error_response_handling(self):
        """Test that API errors are properly returned."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            error_response = Mock()
            error_response.status_code = 404
            error_response.json.return_value = {
                "status": 404,
                "message": "Product not found"
            }
            mock_client_instance.send.return_value = error_response

            result = await salla_get_product(
                GetProductInput(product_id=99999),
                mock_ctx
            )

            assert result["status"] == 404
            assert result["message"] == "Product not found"

    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test that validation errors are handled."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            validation_response = Mock()
            validation_response.status_code = 422
            validation_response.json.return_value = {
                "message": "Validation failed",
                "errors": {
                    "name": ["Name is required"],
                    "price": ["Price must be positive"]
                }
            }
            mock_client_instance.send.return_value = validation_response

            result = await salla_create_product(
                CreateProductInput(
                    name="X",
                    price=0,
                    product_type=ProductType.PRODUCT
                ),
                mock_ctx
            )

            assert "errors" in result


class TestStoreInfo:
    """End-to-end tests for store info."""

    @pytest.mark.asyncio
    async def test_get_store_info_workflow(self):
        """Test getting store information."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers.get.return_value = "Bearer valid-token"

        with patch("mcp_server.salla_client.get_shared_client") as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_get_client.return_value = mock_client_instance
            mock_client_instance.build_request.return_value = Mock()

            store_response = Mock()
            store_response.status_code = 200
            store_response.json.return_value = {
                "data": {
                    "id": 12345,
                    "name": "My Awesome Store",
                    "domain": "mystore.salla.sa",
                    "plan": "premium",
                    "currency": "SAR"
                }
            }
            mock_client_instance.send.return_value = store_response

            result = await salla_get_store_info(mock_ctx)

            assert result["data"]["name"] == "My Awesome Store"
            assert result["data"]["currency"] == "SAR"
