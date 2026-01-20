"""Authentication service for handling OAuth and token management.

This module encapsulates all logic related to Salla OAuth flow,
token exchange, refreshing, and storage.
"""

from datetime import datetime, timedelta, timezone
import secrets
import urllib.parse
from typing import Optional, Dict, Any

import httpx

from ..core import settings, logger
from ..core import (
    get_token_repository,
    get_state_repository,
)


# Get repository instances
_token_repo = get_token_repository()
_state_repo = get_state_repository()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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

    # Use urllib to properly encode parameters
    base_url = settings.salla_oauth_base_url.rstrip("/")
    query_string = urllib.parse.urlencode(params)

    auth_url = f"{base_url}/auth?{query_string}"
    logger.info(f"Generated OAuth URL with redirect_uri: {settings.salla_redirect_uri}")
    return auth_url


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Dict with access_token, refresh_token, expires_in, etc.

    Raises:
        Exception: If token exchange fails
    """
    token_url = f"{settings.salla_oauth_base_url.rstrip('/')}/token"

    payload = {
        "client_id": settings.salla_client_id,
        "client_secret": settings.salla_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.salla_redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            logger.info("Token exchanged successfully")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Token exchange failed: {e.response.text}")
            raise Exception(f"Failed to exchange token: {e.response.text}")
        except Exception as e:
            logger.error(f"Error during token exchange: {str(e)}")
            raise


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh an expired access token.

    Args:
        refresh_token: The refresh token

    Returns:
        Dict with new access_token, refresh_token, expires_in, etc.

    Raises:
        Exception: If token refresh fails
    """
    token_url = f"{settings.salla_oauth_base_url.rstrip('/')}/token"

    payload = {
        "client_id": settings.salla_client_id,
        "client_secret": settings.salla_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "redirect_uri": settings.salla_redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            logger.info("Token refreshed successfully")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Token refresh failed: {e.response.text}")
            raise Exception(f"Failed to refresh token: {e.response.text}")
        except Exception as e:
            logger.error(f"Error during token refresh: {str(e)}")
            raise


async def get_merchant_info(access_token: str) -> Dict[str, Any]:
    """Fetch merchant/store information from Salla API.

    Args:
        access_token: Valid Salla access token

    Returns:
        Dict with merchant info (name, store_name, domain, etc.)
    """
    user_info_url = f"{settings.salla_oauth_base_url.rstrip('/')}/user/info"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(user_info_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch merchant info: {str(e)}")
            return {}


# =============================================================================
# SESSION TOKEN MANAGEMENT
# =============================================================================


async def store_tokens(
    session_id: str,
    tokens: Dict[str, Any],
    merchant_info: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> None:
    """Store tokens for a session.

    Args:
        session_id: Session identifier
        tokens: Token response from Salla (access_token, refresh_token, etc.)
        merchant_info: Optional merchant info to cache
        user_id: Optional user ID to link session to user
    """
    repo = _token_repo

    # Calculate expiry
    expires_in = tokens.get("expires_in", 3600)

    # Always include merchant info if available
    token_data = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
        "scope": tokens.get("scope", ""),
    }

    if merchant_info:
        token_data["merchant_info"] = merchant_info

    await repo.store(
        session_id,
        token_data,
        ttl_seconds=expires_in + 86400,
        user_id=user_id
    )  # Keep for 24h past expiry


async def get_tokens(session_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens for a session.

    Args:
        session_id: Session identifier

    Returns:
        Token data dict or None if not found
    """
    repo = _token_repo
    return await repo.get(session_id)


async def delete_tokens(session_id: str) -> bool:
    """Delete tokens for a session.

    Args:
        session_id: Session identifier

    Returns:
        True if tokens were deleted, False if session not found
    """
    repo = _token_repo
    return await repo.delete(session_id)


async def is_authenticated(session_id: str) -> bool:
    """Check if a session has valid tokens.

    Args:
        session_id: Session identifier

    Returns:
        True if session has non-expired tokens
    """
    token_data = await get_tokens(session_id)
    if not token_data:
        return False

    # Check simple expiry first
    expires_at_str = token_data.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now(timezone.utc) < expires_at:
            return True

    # Attempt refresh if expired but we have refresh token
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        # We assume if we have a refresh token, the session is essentially valid
        # (it will be refreshed on next use via get_valid_access_token)
        return True

    # Expired and no refresh token
    return False


async def get_valid_access_token(session_id: str) -> Optional[str]:
    """Get a valid access token for a session, refreshing if needed.

    Args:
        session_id: Session identifier

    Returns:
        Valid access token or None
    """
    token_data = await get_tokens(session_id)
    if not token_data:
        return None

    access_token = token_data.get("access_token")
    expires_at_str = token_data.get("expires_at")

    # Check if expired
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        # Refresh if expired or expiring in < 5 mins
        if datetime.now(timezone.utc) + timedelta(minutes=5) > expires_at:
            logger.info(f"Token for session {session_id} expired/expiring, refreshing...")
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                try:
                    new_tokens = await refresh_access_token(refresh_token)
                    # Update storage
                    # Preserve merchant info
                    merchant_info = token_data.get("merchant_info")
                    await store_tokens(session_id, new_tokens, merchant_info)
                    return new_tokens.get("access_token")
                except Exception as e:
                    logger.error(f"Failed to refresh token for session {session_id}: {e}")
                    return None

    return access_token


# =============================================================================
# STATE MANAGEMENT FOR CSRF PROTECTION
# =============================================================================


async def store_state(state: str) -> None:
    """Store a state parameter for CSRF validation."""
    repo = _state_repo
    await repo.store(state, ttl_seconds=600)  # 10 minutes


async def validate_state(state: str) -> bool:
    """Validate and consume a state parameter.

    Returns:
        True if state is valid and not expired
    """
    repo = _state_repo
    return await repo.validate_and_consume(state)
