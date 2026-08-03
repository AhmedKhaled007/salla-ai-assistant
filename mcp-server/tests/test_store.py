"""Tests for store tools."""
import pytest
from unittest.mock import patch, AsyncMock

from mcp_server.tools import salla_get_store_info


class TestGetStoreInfo:
    """Tests for salla_get_store_info tool."""

    @pytest.mark.asyncio
    async def test_get_store_info_success(self, mock_context):
        """Test successful store info retrieval."""
        store_data = {
            "id": 12345,
            "name": "My Store",
            "domain": "mystore.salla.sa",
            "plan": "premium",
            "currency": "SAR",
            "status": "active"
        }
        
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": store_data})
            MockClient.return_value = mock_client

            result = await salla_get_store_info(mock_context)

        assert result["data"]["id"] == 12345
        assert result["data"]["name"] == "My Store"
        assert result["data"]["domain"] == "mystore.salla.sa"

    @pytest.mark.asyncio
    async def test_get_store_info_calls_correct_endpoint(self, mock_context):
        """Test that correct API endpoint is called."""
        with patch("mcp_server.utils.SallaClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value={"data": {}})
            MockClient.return_value = mock_client

            await salla_get_store_info(mock_context)

            mock_client.get.assert_called_once_with("/store/info")

    @pytest.mark.asyncio
    async def test_get_store_info_auth_error(self, mock_context_no_auth):
        """Test store info without authentication."""
        result = await salla_get_store_info(mock_context_no_auth)
        
        assert "error" in result
