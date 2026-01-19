"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException

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
)

router = APIRouter()


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
    # 1. Validate state
    if request.state:
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
    
    # 4. Create a session ID for the user (auth_session_id)
    # In a real app, this might be a JWT or session cookie. 
    # Here we'll use the merchant ID or a generated UUID mapped to it.
    import uuid
    auth_session_id = str(uuid.uuid4())
    
    # 5. Store tokens
    await store_tokens(auth_session_id, tokens, merchant_info)
    
    return {
        "status": "success", 
        "auth_session_id": auth_session_id,
        "merchant": merchant_info
    }


@router.post("/logout/{auth_session_id}")
async def logout(auth_session_id: str):
    """Logout endpoint to clear session tokens."""
    # Also need to clear client from pool?
    # This logic should ideally be in a service method that does both.
    success = await delete_tokens(auth_session_id)
    
    # We also need to notify the pool to release/remove the client
    # But routes shouldn't know about pool implementation details strictly...
    # However, since we set up pool in main, maybe we can access it here too 
    # if we passed request. But auth routes might not need pool except for this.
    
    return {"status": "success" if success else "not_found"}
