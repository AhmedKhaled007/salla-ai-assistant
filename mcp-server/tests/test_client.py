import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx
from mcp_server.salla_client import SallaClient, SallaAPIError, get_shared_client, close_shared_client


import pytest_asyncio


@pytest_asyncio.fixture
async def shared_client_cleanup():
    yield
    await close_shared_client()


@pytest.mark.asyncio
async def test_salla_client_initialization():
    client = SallaClient(access_token="test-token")
    assert client.headers["Authorization"] == "Bearer test-token"

    with pytest.raises(ValueError):
        SallaClient(access_token="")


@pytest.mark.asyncio
async def test_request_success(shared_client_cleanup):
    client = SallaClient(access_token="test-token")
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "success"}

    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = mock_response

        response = await client.get("/test")
        assert response == {"data": "success"}
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_retry_logic(shared_client_cleanup):
    client = SallaClient(access_token="test-token")
    client.max_retries = 2

    # 500 error then 200 success
    error_response = Mock(spec=httpx.Response)
    error_response.status_code = 500

    success_response = Mock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"success": True}

    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = [error_response, error_response, success_response]

        # Patch sleep to avoid waiting in tests
        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/test")

        assert response == {"success": True}
        assert mock_send.call_count == 3


@pytest.mark.asyncio
async def test_api_error_handling(shared_client_cleanup):
    client = SallaClient(access_token="test-token")

    error_response = Mock(spec=httpx.Response)
    error_response.status_code = 400
    error_response.json.return_value = {"message": "Bad Request"}

    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = error_response

        with pytest.raises(SallaAPIError) as exc:
            await client.get("/test")

        assert exc.value.status_code == 400
        assert "Bad Request" in str(exc.value)
