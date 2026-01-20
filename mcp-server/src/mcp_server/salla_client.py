"""Salla API HTTP client wrapper."""
from typing import Any, Optional
import asyncio
import httpx

from .config import settings


class SallaAPIError(Exception):
    """Custom exception for Salla API errors."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Salla API Error {status_code}: {message}")


# HTTP connection limits for pooling
_HTTP_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=100,
    keepalive_expiry=30.0,
)


class SallaClient:
    """HTTP client for Salla API with per-request authentication.
    
    Each request should create its own SallaClient instance with the appropriate
    access token to prevent token leakage between concurrent requests.
    
    Features:
    - HTTP connection pooling for better performance
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
        self.base_url = settings.salla_api_base_url
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
        """Make HTTP request to Salla API with retry logic.
        
        Retries on:
        - 5xx server errors
        - 408 Request Timeout
        - 429 Too Many Requests
        - Connection errors
        - Timeout errors
        
        Does NOT retry on:
        - 4xx client errors (except 408, 429)
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    limits=_HTTP_LIMITS,
                ) as client:
                    if method == "GET":
                        response = await client.get(endpoint, params=params)
                    elif method == "POST":
                        response = await client.post(endpoint, json=data)
                    elif method == "PUT":
                        response = await client.put(endpoint, json=data)
                    elif method == "DELETE":
                        response = await client.delete(endpoint)
                    else:
                        raise ValueError(f"Unknown HTTP method: {method}")
                    
                    # Check if we should retry based on status code
                    if self._is_retryable_error(response.status_code) and attempt < self.max_retries:
                        wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s
                        await asyncio.sleep(wait_time)
                        continue
                    
                    return self._handle_response(response)
                    
            except (httpx.ConnectError, httpx.TimeoutException, ConnectionError, OSError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in HTTP request")
    
    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle API response and raise errors if needed."""
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}
        
        if response.status_code >= 400:
            error_msg = data.get("message", "Unknown error")
            raise SallaAPIError(response.status_code, error_msg, data)
        
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
