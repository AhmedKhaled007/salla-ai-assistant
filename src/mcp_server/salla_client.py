"""Salla API HTTP client wrapper."""
from typing import Any, Optional
import httpx

from .config import settings


class SallaAPIError(Exception):
    """Custom exception for Salla API errors."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Salla API Error {status_code}: {message}")


class SallaClient:
    """HTTP client for Salla API with authentication."""
    
    def __init__(self):
        self.base_url = settings.salla_api_base_url
        self.timeout = settings.api_timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> dict:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {settings.salla_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
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
        client = await self._get_client()
        response = await client.get(endpoint, params=params)
        return self._handle_response(response)
    
    async def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make POST request to Salla API."""
        client = await self._get_client()
        response = await client.post(endpoint, json=data)
        return self._handle_response(response)
    
    async def put(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make PUT request to Salla API."""
        client = await self._get_client()
        response = await client.put(endpoint, json=data)
        return self._handle_response(response)
    
    async def delete(self, endpoint: str) -> dict:
        """Make DELETE request to Salla API."""
        client = await self._get_client()
        response = await client.delete(endpoint)
        return self._handle_response(response)


# Singleton instance
salla_client = SallaClient()
