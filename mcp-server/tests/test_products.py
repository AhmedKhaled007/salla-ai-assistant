"""Tests for product tools."""
import pytest
from unittest.mock import patch, AsyncMock

from mcp_server.tools import (
    salla_list_products,
    salla_get_product,
    salla_create_product,
    salla_update_product,
)
from mcp_server.models import (
    ListProductsInput,
    GetProductInput,
    CreateProductInput,
    UpdateProductInput,
    ProductType,
)


class TestListProducts:
    """Tests for salla_list_products tool."""

    @pytest.mark.asyncio
    async def test_list_products_success(self, mock_context, sample_product, sample_pagination):
        """Test successful product listing."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={
                "data": [sample_product],
                "pagination": sample_pagination
            })
            MockClient.return_value = mock_client

            params = ListProductsInput()
            result = await salla_list_products(params, mock_context)

        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == 12345

    @pytest.mark.asyncio
    async def test_list_products_with_filters(self, mock_context):
        """Test product listing with filters."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListProductsInput(
                keyword="phone",
                status="sale",
                category="electronics",
                page=2,
                per_page=25
            )
            await salla_list_products(params, mock_context)

            # Verify correct params passed
            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["keyword"] == "phone"
            assert request_params["status"] == "sale"
            assert request_params["page"] == 2
            assert request_params["per_page"] == 25

    @pytest.mark.asyncio
    async def test_list_products_empty_result(self, mock_context):
        """Test empty product listing."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": [], "pagination": {}})
            MockClient.return_value = mock_client

            params = ListProductsInput()
            result = await salla_list_products(params, mock_context)

        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_list_products_auth_error(self, mock_context_no_auth):
        """Test listing products without authentication."""
        params = ListProductsInput()
        result = await salla_list_products(params, mock_context_no_auth)
        
        assert "error" in result


class TestGetProduct:
    """Tests for salla_get_product tool."""

    @pytest.mark.asyncio
    async def test_get_product_success(self, mock_context, sample_product):
        """Test successful product retrieval."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": sample_product})
            MockClient.return_value = mock_client

            params = GetProductInput(product_id=12345)
            result = await salla_get_product(params, mock_context)

        assert result["data"]["id"] == 12345
        assert result["data"]["name"] == "Test Product"

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, mock_context):
        """Test product not found error."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={
                "status": 404,
                "message": "Product not found"
            })
            MockClient.return_value = mock_client

            params = GetProductInput(product_id=99999)
            result = await salla_get_product(params, mock_context)

        assert result["status"] == 404


class TestCreateProduct:
    """Tests for salla_create_product tool."""

    @pytest.mark.asyncio
    async def test_create_product_minimal(self, mock_context):
        """Test creating product with minimal fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={
                "data": {"id": 123, "name": "New Product"}
            })
            MockClient.return_value = mock_client

            params = CreateProductInput(
                name="New Product",
                price=99.99,
                product_type=ProductType.PRODUCT
            )
            result = await salla_create_product(params, mock_context)

        assert result["data"]["id"] == 123

    @pytest.mark.asyncio
    async def test_create_product_full(self, mock_context):
        """Test creating product with all fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {"id": 456}})
            MockClient.return_value = mock_client

            params = CreateProductInput(
                name="Full Product",
                price=199.99,
                product_type=ProductType.SERVICE,
                quantity=50,
                description="Full description",
                sku="SKU-001",
                status="sale",
                sale_price=149.99
            )
            await salla_create_product(params, mock_context)

            # Verify payload
            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            assert data["name"] == "Full Product"
            assert data["price"] == 199.99
            assert data["product_type"] == "service"
            assert data["quantity"] == 50

    @pytest.mark.asyncio
    async def test_create_product_enum_conversion(self, mock_context):
        """Test product type enum is converted to string."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = CreateProductInput(
                name="Digital Product",
                price=50,
                product_type=ProductType.DIGITAL
            )
            await salla_create_product(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            assert data["product_type"] == "digital"  # String, not enum


class TestUpdateProduct:
    """Tests for salla_update_product tool."""

    @pytest.mark.asyncio
    async def test_update_product_success(self, mock_context):
        """Test successful product update."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.put = AsyncMock(return_value={
                "data": {"id": 123, "price": 79.99}
            })
            MockClient.return_value = mock_client

            params = UpdateProductInput(product_id=123, price=79.99)
            result = await salla_update_product(params, mock_context)

        assert result["data"]["price"] == 79.99

    @pytest.mark.asyncio
    async def test_update_product_partial(self, mock_context):
        """Test partial product update only sends changed fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.put = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = UpdateProductInput(product_id=123, quantity=50)
            await salla_update_product(params, mock_context)

            call_args = mock_client.put.call_args
            data = call_args[1]["data"]
            assert "quantity" in data
            assert "name" not in data
            assert "price" not in data

    @pytest.mark.asyncio
    async def test_update_product_no_fields(self, mock_context):
        """Test update with no fields returns error."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            params = UpdateProductInput(product_id=123)
            result = await salla_update_product(params, mock_context)

        assert "error" in result
        assert "No fields provided" in result["error"]
