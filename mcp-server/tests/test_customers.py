"""Tests for customer tools."""
import pytest
from unittest.mock import patch, AsyncMock

from mcp_server.tools import (
    salla_list_customers,
    salla_get_customer,
    salla_create_customer,
)
from mcp_server.models import (
    ListCustomersInput,
    GetCustomerInput,
    CreateCustomerInput,
)


class TestListCustomers:
    """Tests for salla_list_customers tool."""

    @pytest.mark.asyncio
    async def test_list_customers_success(self, mock_context, sample_customer, sample_pagination):
        """Test successful customer listing."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={
                "data": [sample_customer],
                "pagination": sample_pagination
            })
            MockClient.return_value = mock_client

            params = ListCustomersInput()
            result = await salla_list_customers(params, mock_context)

        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == 111

    @pytest.mark.asyncio
    async def test_list_customers_with_keyword(self, mock_context):
        """Test customer listing with keyword search."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListCustomersInput(keyword="ahmed@example.com")
            await salla_list_customers(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["keyword"] == "ahmed@example.com"

    @pytest.mark.asyncio
    async def test_list_customers_pagination(self, mock_context):
        """Test customer listing pagination."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListCustomersInput(page=3, per_page=50)
            await salla_list_customers(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["page"] == 3
            assert request_params["per_page"] == 50

    @pytest.mark.asyncio
    async def test_list_customers_date_filters(self, mock_context):
        """Test customer listing with date filters."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": []})
            MockClient.return_value = mock_client

            params = ListCustomersInput(
                date_from="2024-01-01",
                date_to="2024-06-30"
            )
            await salla_list_customers(params, mock_context)

            call_args = mock_client.get.call_args
            request_params = call_args[1]["params"]
            assert request_params["date_from"] == "2024-01-01"
            assert request_params["date_to"] == "2024-06-30"


class TestGetCustomer:
    """Tests for salla_get_customer tool."""

    @pytest.mark.asyncio
    async def test_get_customer_success(self, mock_context, sample_customer):
        """Test successful customer retrieval."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": sample_customer})
            MockClient.return_value = mock_client

            params = GetCustomerInput(customer_id=111)
            result = await salla_get_customer(params, mock_context)

        assert result["data"]["id"] == 111
        assert result["data"]["first_name"] == "Ahmed"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, mock_context):
        """Test customer not found error."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={
                "status": 404,
                "message": "Customer not found"
            })
            MockClient.return_value = mock_client

            params = GetCustomerInput(customer_id=99999)
            result = await salla_get_customer(params, mock_context)

        assert result["status"] == 404


class TestCreateCustomer:
    """Tests for salla_create_customer tool."""

    @pytest.mark.asyncio
    async def test_create_customer_minimal(self, mock_context):
        """Test creating customer with minimal fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={
                "data": {"id": 222, "first_name": "Ali"}
            })
            MockClient.return_value = mock_client

            params = CreateCustomerInput(
                first_name="Ali",
                last_name="Mohamed",
                mobile="500000000",
                mobile_code_country="+966"
            )
            result = await salla_create_customer(params, mock_context)

        assert result["data"]["id"] == 222

    @pytest.mark.asyncio
    async def test_create_customer_full(self, mock_context):
        """Test creating customer with all fields."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {"id": 333}})
            MockClient.return_value = mock_client

            params = CreateCustomerInput(
                first_name="Ahmed",
                last_name="Khaled",
                mobile="500000000",
                mobile_code_country="+966",
                email="ahmed@example.com",
                gender="male",
                birthday="1990-05-15",
                groups=[1, 2]
            )
            await salla_create_customer(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            
            assert data["first_name"] == "Ahmed"
            assert data["last_name"] == "Khaled"
            assert data["email"] == "ahmed@example.com"
            assert data["gender"] == "male"
            assert data["birthday"] == "1990-05-15"
            assert data["groups"] == [1, 2]

    @pytest.mark.asyncio
    async def test_create_customer_excludes_empty_strings(self, mock_context):
        """Test that empty optional strings are excluded from payload."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            params = CreateCustomerInput(
                first_name="Test",
                last_name="User",
                mobile="500000000",
                mobile_code_country="+966"
                # email, gender, birthday left as default empty strings
            )
            await salla_create_customer(params, mock_context)

            call_args = mock_client.post.call_args
            data = call_args[1]["data"]
            
            # Empty strings should not be in payload
            assert "email" not in data or data.get("email") != ""
            assert "gender" not in data or data.get("gender") != ""

    @pytest.mark.asyncio
    async def test_create_customer_auth_error(self, mock_context_no_auth):
        """Test creating customer without authentication."""
        params = CreateCustomerInput(
            first_name="Test",
            last_name="User",
            mobile="500000000",
            mobile_code_country="+966"
        )
        result = await salla_create_customer(params, mock_context_no_auth)
        
        assert "error" in result
