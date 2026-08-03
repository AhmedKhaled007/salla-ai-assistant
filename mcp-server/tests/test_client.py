"""Tests for SallaClient HTTP client."""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx

from mcp_server.salla_client import SallaClient, get_shared_client, close_shared_client


class TestSallaClientInitialization:
    """Tests for SallaClient initialization."""

    def test_valid_initialization(self):
        """Test client initializes with valid token."""
        client = SallaClient(access_token="valid-token")
        assert client._access_token == "valid-token"

    def test_empty_token_raises(self):
        """Test empty token raises ValueError."""
        with pytest.raises(ValueError, match="Access token is required"):
            SallaClient(access_token="")

    def test_none_token_raises(self):
        """Test None token raises ValueError."""
        with pytest.raises(ValueError, match="Access token is required"):
            SallaClient(access_token=None)

    def test_headers_contain_auth(self):
        """Test headers contain proper Authorization."""
        client = SallaClient(access_token="my-token")
        headers = client.headers
        assert headers["Authorization"] == "Bearer my-token"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"


class TestSallaClientRequests:
    """Tests for SallaClient HTTP requests."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup shared client after each test."""
        yield
        await close_shared_client()

    @pytest.mark.asyncio
    async def test_get_request_success(self, mock_httpx_response):
        """Test successful GET request."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(200, {"data": [{"id": 1}]})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.get("/products")

        assert result == {"data": [{"id": 1}]}
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_request_with_params(self, mock_httpx_response):
        """Test GET request with query parameters."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(200, {"data": []})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            await client.get("/products", params={"page": 1, "per_page": 10})

        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_request_success(self, mock_httpx_response):
        """Test successful POST request."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(201, {"data": {"id": 123}})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.post("/products", data={"name": "Test"})

        assert result["data"]["id"] == 123

    @pytest.mark.asyncio
    async def test_put_request_success(self, mock_httpx_response):
        """Test successful PUT request."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(200, {"data": {"updated": True}})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.put("/products/123", data={"name": "Updated"})

        assert result["data"]["updated"] is True

    @pytest.mark.asyncio
    async def test_delete_request_success(self, mock_httpx_response):
        """Test successful DELETE request."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(200, {"success": True})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.delete("/products/123")

        assert result["success"] is True


class TestSallaClientRetryLogic:
    """Tests for SallaClient retry logic."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup shared client after each test."""
        yield
        await close_shared_client()

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, mock_httpx_response):
        """Test retry on 500 server error."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 2

        error_response = mock_httpx_response(500, {"error": "Server Error"})
        success_response = mock_httpx_response(200, {"data": "success"})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [error_response, success_response]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get("/test")

        assert result == {"data": "success"}
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self, mock_httpx_response):
        """Test retry on 429 rate limit error."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 1

        rate_limit_response = mock_httpx_response(429, {"error": "Rate limited"})
        success_response = mock_httpx_response(200, {"data": "ok"})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [rate_limit_response, success_response]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get("/test")

        assert result == {"data": "ok"}
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self, mock_httpx_response):
        """Test no retry on 400 client error."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 3

        error_response = mock_httpx_response(400, {"error": "Bad Request"})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = error_response
            result = await client.get("/test")

        # Should return error response without retrying
        assert result["error"] == "Bad Request"
        assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, mock_httpx_response):
        """Test behavior when max retries are exhausted."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 2

        error_response = mock_httpx_response(500, {"error": "Server Error"})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = error_response
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get("/test")

        # After retries exhausted, returns error response
        assert result["error"] == "Server Error"
        assert mock_send.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, mock_httpx_response):
        """Test retry on connection errors."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 1

        success_response = mock_httpx_response(200, {"data": "success"})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [
                httpx.ConnectError("Connection failed"),
                success_response
            ]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get("/test")

        assert result == {"data": "success"}
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_after_retries_raises(self, mock_httpx_response):
        """Test connection error is raised after retries exhausted."""
        client = SallaClient(access_token="test-token")
        client.max_retries = 1

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = httpx.ConnectError("Connection failed")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(httpx.ConnectError):
                    await client.get("/test")


class TestSallaClientResponseHandling:
    """Tests for SallaClient response handling."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup shared client after each test."""
        yield
        await close_shared_client()

    @pytest.mark.asyncio
    async def test_json_response_parsed(self, mock_httpx_response):
        """Test JSON response is properly parsed."""
        client = SallaClient(access_token="test-token")
        mock_response = mock_httpx_response(200, {"key": "value", "nested": {"a": 1}})

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.get("/test")

        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    @pytest.mark.asyncio
    async def test_non_json_response_returns_raw(self):
        """Test non-JSON response returns raw text."""
        client = SallaClient(access_token="test-token")
        
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"

        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await client.get("/test")

        assert result == {"raw": "Plain text response"}


class TestSharedClient:
    """Tests for shared client management."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        """Cleanup shared client after each test."""
        yield
        await close_shared_client()

    @pytest.mark.asyncio
    async def test_get_shared_client_creates_client(self):
        """Test get_shared_client creates a client."""
        client = await get_shared_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_get_shared_client_reuses_client(self):
        """Test get_shared_client returns the same client."""
        client1 = await get_shared_client()
        client2 = await get_shared_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_shared_client_closes(self):
        """Test close_shared_client properly closes the client."""
        client = await get_shared_client()
        await close_shared_client()
        assert client.is_closed

    @pytest.mark.asyncio
    async def test_close_then_get_creates_new_client(self):
        """Test getting client after close creates a new one."""
        client1 = await get_shared_client()
        await close_shared_client()
        client2 = await get_shared_client()
        assert client1 is not client2
