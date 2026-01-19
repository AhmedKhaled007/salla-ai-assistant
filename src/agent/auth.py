"""Salla OAuth 2.0 authentication helpers.

This module provides functions for:
- Generating Salla OAuth authorization URLs
- Exchanging authorization codes for access tokens
- Refreshing expired tokens
- Managing per-session token storage via repositories
"""

import secrets
import httpx
from typing import Optional
from datetime import datetime, timedelta

from .utils import settings, logger
from .dependencies import get_token_repository, get_state_repository


# Get repository instances
_token_repo = get_token_repository()
_state_repo = get_state_repository()


def generate_state() -> str:
    """Generate a cryptographically secure state parameter."""
    return secrets.token_urlsafe(32)


def generate_auth_url(state: str) -> str:
    """Build the Salla OAuth authorization URL.
    
    Args:
        state: CSRF protection state parameter
        
    Returns:
        Full authorization URL to redirect user to
    """
    params = {
        "client_id": settings.salla_client_id,
        "redirect_uri": settings.salla_redirect_uri,
        "response_type": "code",
        "scope": settings.salla_scopes,
        "state": state,
    }
    
    from urllib.parse import urlencode
    query_string = urlencode(params)
    return f"{settings.salla_oauth_base_url}/auth?{query_string}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from OAuth callback
        
    Returns:
        Dict with access_token, refresh_token, expires_in, etc.
        
    Raises:
        Exception: If token exchange fails
    """
    token_url = f"{settings.salla_oauth_base_url}/token"
    
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.salla_client_id,
        "client_secret": settings.salla_client_secret,
        "code": code,
        "redirect_uri": settings.salla_redirect_uri,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Token exchange failed"))
            logger.error(f"Token exchange failed: {response.status_code} - {error_msg}")
            raise Exception(error_msg)
        
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token.
    
    Args:
        refresh_token: The refresh token
        
    Returns:
        Dict with new access_token, refresh_token, expires_in, etc.
        
    Raises:
        Exception: If token refresh fails
    """
    token_url = f"{settings.salla_oauth_base_url}/token"
    
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.salla_client_id,
        "client_secret": settings.salla_client_secret,
        "refresh_token": refresh_token,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Token refresh failed"))
            logger.error(f"Token refresh failed: {response.status_code} - {error_msg}")
            raise Exception(error_msg)
        
        return response.json()


async def get_merchant_info(access_token: str) -> dict:
    """Fetch merchant/store information from Salla API.
    
    Args:
        access_token: Valid Salla access token
        
    Returns:
        Dict with merchant info (name, store_name, domain, etc.)
    """
    api_url = "https://api.salla.dev/admin/v2/store/info"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            api_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch merchant info: {response.status_code}")
            return {}
        
        data = response.json()
        return data.get("data", {})


# =============================================================================
# SESSION TOKEN MANAGEMENT (using TokenRepository)
# =============================================================================


async def store_tokens(
    session_id: str, tokens: dict, merchant_info: Optional[dict] = None
) -> None:
    """Store tokens for a session.
    
    Args:
        session_id: Session identifier
        tokens: Token response from Salla (access_token, refresh_token, etc.)
        merchant_info: Optional merchant info to cache
    """
    expires_in = tokens.get("expires_in", 3600)
    token_data = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
        "merchant_info": merchant_info,
    }
    await _token_repo.store(session_id, token_data, ttl_seconds=expires_in)
    logger.info(f"Stored tokens for session: {session_id[:8]}...")


async def get_tokens(session_id: str) -> Optional[dict]:
    """Get tokens for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Token data dict or None if not found
    """
    return await _token_repo.get(session_id)


async def delete_tokens(session_id: str) -> bool:
    """Delete tokens for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if tokens were deleted, False if session not found
    """
    deleted = await _token_repo.delete(session_id)
    if deleted:
        logger.info(f"Deleted tokens for session: {session_id[:8]}...")
    return deleted


async def is_authenticated(session_id: str) -> bool:
    """Check if a session has valid tokens.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if session has non-expired tokens
    """
    token_data = await _token_repo.get(session_id)
    if not token_data:
        return False
    
    # Check if token is expired (with 5 minute buffer)
    expires_at_str = token_data.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now() > expires_at - timedelta(minutes=5):
            return False
    
    return bool(token_data.get("access_token"))


async def get_valid_access_token(session_id: str) -> Optional[str]:
    """Get a valid access token for a session, refreshing if needed.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Valid access token or None
    """
    token_data = await _token_repo.get(session_id)
    if not token_data:
        return None
    
    # Check if token is about to expire (5 minute buffer)
    expires_at_str = token_data.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now() > expires_at - timedelta(minutes=5):
            # Try to refresh
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                try:
                    new_tokens = await refresh_access_token(refresh_token)
                    await store_tokens(session_id, new_tokens, token_data.get("merchant_info"))
                    return new_tokens.get("access_token")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    await delete_tokens(session_id)
                    return None
            else:
                return None
    
    return token_data.get("access_token")


# =============================================================================
# STATE MANAGEMENT FOR CSRF PROTECTION (using StateRepository)
# =============================================================================


async def store_state(state: str) -> None:
    """Store a state parameter for CSRF validation."""
    await _state_repo.store(state, ttl_seconds=600)  # 10 minutes


async def validate_state(state: str) -> bool:
    """Validate and consume a state parameter.
    
    Returns:
        True if state is valid and not expired
    """
    return await _state_repo.validate_and_consume(state)
