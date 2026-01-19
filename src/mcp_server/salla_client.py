"""Salla API HTTP client wrapper."""
from typing import Any, Optional
from contextvars import ContextVar
import httpx

from .config import settings


# Context variable to store the current request's access token
_current_access_token: ContextVar[Optional[str]] = ContextVar('current_access_token', default=None)


def set_access_token(token: str):
    """Set the access token for the current request context."""
    _current_access_token.set(token)


def get_access_token() -> Optional[str]:
    """Get the access token for the current request context."""
    return _current_access_token.get()


class SallaAPIError(Exception):
    """Custom exception for Salla API errors."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Salla API Error {status_code}: {message}")


class SallaClient:
    """HTTP client for Salla API with per-request authentication."""
    
    def __init__(self, access_token: Optional[str] = None):
        """Initialize client with optional access token.
        
        Args:
            access_token: Salla API access token. If None, will try to get from
                         context variable or fall back to settings.
        """
        self.base_url = settings.salla_api_base_url
        self.timeout = settings.api_timeout
        self._access_token = access_token
    
    @property
    def access_token(self) -> str:
        """Get access token from instance, context, or settings."""
        if self._access_token:
            return self._access_token
        context_token = get_access_token()
        if context_token:
            return context_token
        return settings.salla_access_token
    
    @property
    def headers(self) -> dict:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None, data: Optional[dict] = None) -> dict:
        """Make HTTP request to Salla API."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
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
            
            return self._handle_response(response)
    
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


# Default client instance (uses context variable or settings for token)
salla_client = SallaClient()
