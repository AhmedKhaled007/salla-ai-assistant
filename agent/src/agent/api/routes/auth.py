
from fastapi import APIRouter, HTTPException, Depends, Header
import uuid

from ..models import OAuthCallbackRequest
from ...services import (
    generate_state,
    store_state,
    generate_auth_url,
    validate_state,
    exchange_code_for_tokens,
    get_merchant_info,
    store_tokens,
    delete_tokens,
    is_authenticated,
    get_tokens
)
from ...core import get_user_repository

router = APIRouter()


async def get_auth_session_id(
    x_auth_session_id: str | None = Header(default=None, alias="X-Auth-Session-Id")
) -> str | None:
    if not x_auth_session_id:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Session-Id header")
    return x_auth_session_id


async def get_optional_auth_session_id(
    x_auth_session_id: str | None = Header(default=None, alias="X-Auth-Session-Id")
) -> str | None:
    """Optional auth - returns None if header is missing instead of raising."""
    return x_auth_session_id


@router.get("/url")
async def get_auth_url_endpoint():
    """Get the Salla OAuth authorization URL.

    Returns the URL to redirect the user to for Salla authorization.
    Includes a state parameter for CSRF protection.
    """
    state = generate_state()
    await store_state(state)

    url = generate_auth_url(state)
    return {"url": url}


@router.post("/callback")
async def oauth_callback_endpoint(request: OAuthCallbackRequest):
    """Handle OAuth callback from Salla.

    Exchanges the authorization code for access and refresh tokens.
    Validates CSRF state parameter for security.
    Returns merchant info on success.
    """
    # 1. Validate state (REQUIRED for CSRF protection)
    if not request.state:
        raise HTTPException(status_code=400, detail="Missing required CSRF state parameter")

    if not await validate_state(request.state):
        raise HTTPException(status_code=400, detail="Invalid or expired CSRF state")

    # 2. Exchange code for tokens
    try:
        tokens = await exchange_code_for_tokens(request.code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Get merchant info
    access_token = tokens["access_token"]
    merchant_info = await get_merchant_info(access_token)

    # 4. Create/Update User
    user_id = None
    if merchant_info:
        user_repo = get_user_repository()
        # Ensure we have the required unique ID
        salla_user_id = str(merchant_info.get("id"))
        if salla_user_id:
            user_data = {
                "name": merchant_info.get("name"),
                "email": merchant_info.get("email"),
                "store_name": merchant_info.get("store", {}).get("name"),  # Adjust based on actual payload structure
                "domain": merchant_info.get("store", {}).get("domain"),
            }
            user = await user_repo.create_or_update(salla_user_id, user_data)
            user_id = user.id

    # 5. Create a session ID for the user (auth_session_id)
    auth_session_id = str(uuid.uuid4())

    # 6. Store tokens with user_id
    await store_tokens(auth_session_id, tokens, merchant_info, user_id=user_id)

    return {
        "status": "success",
        "auth_session_id": auth_session_id,
        "merchant": merchant_info
    }


@router.get("/status")
async def get_auth_status(
    auth_session_id: str | None = Depends(get_optional_auth_session_id)
):
    """Check authentication status using header."""
    if not auth_session_id:
        return {"authenticated": False}

    authenticated = await is_authenticated(auth_session_id)
    if not authenticated:
        return {"authenticated": False}

    tokens = await get_tokens(auth_session_id)
    merchant_info = tokens.get("merchant_info") if tokens else None

    return {
        "authenticated": True,
        "merchant_info": merchant_info
    }


@router.post("/logout")
async def logout(
    auth_session_id: str | None = Depends(get_auth_session_id)
):
    """Logout endpoint to clear session tokens."""
    if not auth_session_id:
        return {"status": "success"}

    success = await delete_tokens(auth_session_id)
    return {"status": "success" if success else "not_found"}
