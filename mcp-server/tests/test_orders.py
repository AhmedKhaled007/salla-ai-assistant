"""Tests for order tools."""
import pytest
from unittest.mock import patch, AsyncMock

from mcp_server.tools import (
    salla_list_orders,
    salla_get_order,
    salla_create_order,
    salla_update_order_status,
)
from mcp_server.models import (
    ListOrdersInput,
    GetOrderInput,
    CreateOrderInput,
    UpdateOrderStatusInput,
    OrderProduct,
    DeliveryMethod,
    PaymentMethod,
)


class TestListOrders:
    """Tests for salla_list_orders tool."""

    @pytest.mark.asyncio
    async def test_list_orders_success(self, mock_context, sample_order, sample_pagination):
        """Test successful order listing."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={
                "data": [sample_order],
                "pagination": sample_pagination
            })
            MockClient.return_value = mock_client

            params = ListOrdersInput()
            result = await salla_list_orders(params, mock_context)

        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == 67890

    @pytest.mark.asyncio
    async def test_list_orders_with_status_filter(self, mock_context):
        """Test order listing with status filter."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListOrdersInput(status="pending,processing")
            await salla_list_orders(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            # Comma-separated status should be split into list
            assert request_params["status"] == ["pending", "processing"]

    @pytest.mark.asyncio
    async def test_list_orders_with_date_range(self, mock_context):
        """Test order listing with date range filter."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListOrdersInput(
                from_date="2024-01-01",
                to_date="2024-12-31"
            )
            await salla_list_orders(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["from_date"] == "2024-01-01"
            assert request_params["to_date"] == "2024-12-31"


class TestGetOrder:
    """Tests for salla_get_order tool."""

    @pytest.mark.asyncio
    async def test_get_order_success(self, mock_context, sample_order):
        """Test successful order retrieval."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": sample_order})
            MockClient.return_value = mock_client

            params = GetOrderInput(order_id=67890)
            result = await salla_get_order(params, mock_context)

        assert result["data"]["id"] == 67890
        assert result["data"]["reference_id"] == "ORD-2024-001"

    @pytest.mark.asyncio
    async def test_get_order_light_format(self, mock_context):
        """Test order retrieval with light format."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = GetOrderInput(order_id=123, format="light")
            await salla_get_order(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["format"] == "light"


class TestCreateOrder:
    """Tests for salla_create_order tool."""

    @pytest.mark.asyncio
    async def test_create_order_minimal(self, mock_context):
        """Test creating order with minimal fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={
                "data": {"id": 12345, "status": "pending"}
            })
            MockClient.return_value = mock_client

            params = CreateOrderInput(
                customer_id=111,
                products=[OrderProduct(identifier="12345", quantity=2)]
            )
            result = await salla_create_order(params, mock_context)

        assert result["data"]["id"] == 12345

    @pytest.mark.asyncio
    async def test_create_order_payload_structure(self, mock_context):
        """Test order creation payload structure."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = CreateOrderInput(
                customer_id=111,
                products=[
                    OrderProduct(identifier="12345", quantity=2),
                    OrderProduct(identifier="SKU-001", identifier_type="sku", quantity=1)
                ],
                delivery_method=DeliveryMethod.PICKUP,
                payment_method=PaymentMethod.COD
            )
            await salla_create_order(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            
            # Verify structure
            assert data["customer"]["id"] == 111
            assert len(data["products"]) == 2
            assert data["delivery_method"] == "pickup"
            assert data["payment"]["method"] == "cod"
            assert data["payment"]["status"] == "pending_payment"  # COD = pending

    @pytest.mark.asyncio
    async def test_create_order_bank_payment(self, mock_context):
        """Test order with bank payment includes bank details."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = CreateOrderInput(
                customer_id=111,
                products=[OrderProduct(identifier="123")],
                payment_method=PaymentMethod.BANK,
                bank_id=1,
                receipt_image="https://example.com/receipt.jpg"
            )
            await salla_create_order(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            
            assert data["payment"]["method"] == "bank"
            assert data["payment"]["store_bank_id"] == 1
            assert data["payment"]["receipt_image_path"] == "https://example.com/receipt.jpg"


class TestUpdateOrderStatus:
    """Tests for salla_update_order_status tool."""

    @pytest.mark.asyncio
    async def test_update_status_by_id(self, mock_context):
        """Test updating order status by ID."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={
                "data": {"status": {"id": 5, "name": "completed"}}
            })
            MockClient.return_value = mock_client

            params = UpdateOrderStatusInput(order_id=123, status_id=5)
            result = await salla_update_order_status(params, mock_context)

        assert result["data"]["status"]["id"] == 5

    @pytest.mark.asyncio
    async def test_update_status_by_slug(self, mock_context):
        """Test updating order status by slug."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = UpdateOrderStatusInput(order_id=123, slug="completed")
            await salla_update_order_status(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            assert data["slug"] == "completed"

    @pytest.mark.asyncio
    async def test_update_status_with_note(self, mock_context):
        """Test updating order status with a note."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = UpdateOrderStatusInput(
                order_id=123,
                status_id=3,
                note="Customer requested cancellation"
            )
            await salla_update_order_status(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            assert data["note"] == "Customer requested cancellation"

    @pytest.mark.asyncio
    async def test_update_status_missing_both(self, mock_context):
        """Test error when neither status_id nor slug provided."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            params = UpdateOrderStatusInput(order_id=123)
            result = await salla_update_order_status(params, mock_context)

        assert "error" in result
        assert "status_id or slug" in result["error"]

    @pytest.mark.asyncio
    async def test_update_status_restore_items(self, mock_context):
        """Test updating status with restore_items option."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = UpdateOrderStatusInput(
                order_id=123,
                slug="cancelled",
                restore_items=True
            )
            await salla_update_order_status(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            assert data["restore_items"] is True
