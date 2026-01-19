"""FastAPI dependencies."""

from fastapi import Header, HTTPException
from typing import Optional

from ..core import settings


async def verify_api_key(x_api_key: str | None = Header(default=None)):
    """Verify API key if authentication is enabled."""
    if not settings.api_key_enabled:
        return
        
    if not settings.api_key:
        # If enabled but not configured, log warning and fail closed
        raise HTTPException(status_code=500, detail="Server misconfiguration: API key enabled but not set")
        
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
