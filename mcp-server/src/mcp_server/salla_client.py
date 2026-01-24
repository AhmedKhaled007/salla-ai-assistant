"""Salla API HTTP client wrapper."""
from typing import Optional
import asyncio
import httpx
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Global shared client for connection pooling
_SHARED_CLIENT: Optional[httpx.AsyncClient] = None


async def get_shared_client() -> httpx.AsyncClient:
    """Get or create the global shared HTTP client."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30.0,
        )
        _SHARED_CLIENT = httpx.AsyncClient(
            base_url=settings.salla_api_base_url,
            timeout=settings.api_timeout,
            limits=limits,
        )
    return _SHARED_CLIENT


async def close_shared_client():
    """Close the global shared HTTP client."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT:
        await _SHARED_CLIENT.aclose()
        _SHARED_CLIENT = None


class SallaClient:
    """HTTP client for Salla API with per-request authentication.

    Each request should create its own SallaClient instance with the appropriate
    access token to prevent token leakage between concurrent requests.

    Features:
    - HTTP connection pooling (cached globally)
    - Automatic retry with exponential backoff for transient failures
    - Proper error handling for 4xx/5xx responses
    """

    def __init__(self, access_token: str):
        """Initialize client with access token.

        Args:
            access_token: Salla API access token (required)
        """
        if not access_token:
            raise ValueError("Access token is required")
        self.timeout = settings.api_timeout
        self.max_retries = settings.api_max_retries
        self._access_token = access_token

    @property
    def headers(self) -> dict:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _is_retryable_error(self, status_code: int) -> bool:
        """Check if an HTTP status code is retryable.

        5xx errors and certain specific errors are retryable.
        4xx errors (client errors) are NOT retryable.
        """
        return status_code >= 500 or status_code in (408, 429)  # Timeout, Rate limited

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None
    ) -> dict:
        """Make HTTP request to Salla API with retry logic."""
        client = await get_shared_client()
        request = client.build_request(
            method,
            endpoint,
            params=params,
            json=data,
            headers=self.headers,
            timeout=self.timeout
        )
        logger.debug(
            f"Making request with method: {method}\nEndpoint: {endpoint}\nParams: {params}\nData: {data}")

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.send(request)
                # Check if we should retry based on status code
                if self._is_retryable_error(response.status_code) and attempt < self.max_retries:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(f"Request failed with {response.status_code}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                return self._handle_response(response)

            except (httpx.ConnectError, httpx.TimeoutException, ConnectionError, OSError) as e:
                logger.warning(f"Request connection error: {e}, retrying ({attempt + 1}/{self.max_retries})...")
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) * 0.5
                    await asyncio.sleep(wait_time)
                    continue
                raise

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle API response"""
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}
        return data

    async def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make GET request to Salla API."""
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make POST request to Salla API."""
        return await self._request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make PUT request to Salla API."""
        return await self._request("PUT", endpoint, data=data)

    async def delete(self, endpoint: str) -> dict:
        """Make DELETE request to Salla API."""
        return await self._request("DELETE", endpoint)
