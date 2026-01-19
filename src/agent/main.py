"""Agent Service - FastAPI application for AI-powered Salla assistant."""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any
from contextlib import asynccontextmanager
import asyncio
import json
import uuid

from .client_pool import MCPClientPool
from .utils import settings, logger
from .dependencies import get_rate_limit_repository
from . import auth


# Get repository instance
_rate_limit_repo = get_rate_limit_repository()


async def verify_api_key(x_api_key: str | None = Header(default=None)):
    """Verify API key if authentication is enabled."""
    if not settings.api_key_enabled:
        return  # Auth disabled
    
    if not settings.api_key:
        raise HTTPException(
            status_code=500, 
            detail="API key authentication enabled but no API_KEY configured"
        )
    
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown.
    
    Handles:
    - MCPClientPool initialization on startup
    - Cleanup of all pooled resources on shutdown
    
    Note: Uvicorn handles SIGTERM/SIGINT natively and triggers the lifespan
    context manager exit, which runs our finally block for cleanup.
    """
    # Initialize MCPClientPool with configured transport
    pool = MCPClientPool(
        transport=settings.mcp_transport,
        server_url=settings.mcp_server_url if settings.mcp_transport == "http" else None,
        server_script_path=settings.server_script_path,
        max_idle_seconds=300,
        cleanup_interval_seconds=60,
    )
    
    try:
        logger.info(f"Starting agent service with {settings.mcp_transport} transport...")
        initialized = await pool.initialize()
        if not initialized:
            raise RuntimeError("Failed to initialize MCPClientPool")
        app.state.client_pool = pool
        logger.info("Agent service started successfully with MCPClientPool")
        yield
    except Exception as e:
        logger.error(f"Error during lifespan: {e}")
        raise RuntimeError(f"Startup failed: {e}") from e
    finally:
        # Graceful shutdown
        logger.info("Shutting down agent service...")
        await pool.cleanup_all()
        logger.info("Agent service shutdown complete")


app = FastAPI(title="Salla AI Agent API", lifespan=lifespan)


# Add CORS middleware with configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Rate limiting middleware using RateLimitRepository."""
    if not settings.rate_limit_enabled:
        return await call_next(request)
    
    # Get client IP (use X-Forwarded-For if behind proxy)
    client_ip = request.headers.get(
        "X-Forwarded-For", 
        request.client.host if request.client else "unknown"
    )
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    # Check rate limit using repository
    allowed = await _rate_limit_repo.check_and_increment(
        client_ip,
        settings.rate_limit_requests,
        settings.rate_limit_window,
    )
    
    if not allowed:
        remaining = await _rate_limit_repo.get_remaining(
            client_ip, settings.rate_limit_requests, settings.rate_limit_window
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
            headers={
                "Retry-After": str(settings.rate_limit_window),
                "X-RateLimit-Remaining": str(remaining),
            }
        )
    
    return await call_next(request)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for query endpoint with validation."""
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=settings.max_query_length,
        description="The user's query text"
    )
    session_id: str | None = Field(
        default=None, 
        description="Optional conversation session ID to continue existing conversation"
    )
    auth_session_id: str | None = Field(
        default=None,
        description="OAuth session ID for user authentication (from login callback)"
    )


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code from Salla")
    state: str | None = Field(default=None, description="CSRF state parameter")


# =============================================================================
# HEALTH & TOOLS ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer probes.
    
    Performs live ping to MCP server to verify connectivity.
    Returns MCP connection status, LLM availability, and pool info.
    """
    pool: MCPClientPool = app.state.client_pool
    mcp_responsive = await pool.ping()
    
    return {
        "status": "healthy" if mcp_responsive else "degraded",
        "mcp_connected": pool.is_connected,
        "mcp_responsive": mcp_responsive,
        "llm_model": settings.llm_model,
        "pool_size": pool.pool_size,
        "active_clients": pool.active_clients,
    }


@app.get("/tools")
async def get_tools():
    """Get the list of available tools."""
    pool: MCPClientPool = app.state.client_pool
    
    # Use default client to get tools
    client = await pool.get_client(None, None)
    try:
        tools = await client.get_mcp_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QUERY ENDPOINTS (using MCPClientPool)
# =============================================================================

@app.post("/query", dependencies=[Depends(verify_api_key)])
async def process_query(request: QueryRequest):
    """Process a query and return the response.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    If session_id is provided, continues the existing conversation.
    If auth_session_id is provided, uses the user's OAuth token.
    """
    pool: MCPClientPool = app.state.client_pool
    access_token = None
    
    # Get user's OAuth token if authenticated
    if request.auth_session_id:
        access_token = await auth.get_valid_access_token(request.auth_session_id)
    
    # Get or create client for this user
    client = await pool.get_client(request.auth_session_id, access_token)
    
    try:
        session_id, messages = await client.process_query(
            request.query, request.session_id
        )
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await pool.release_client(request.auth_session_id)


@app.post("/query/stream", dependencies=[Depends(verify_api_key)])
async def process_query_stream(request: QueryRequest):
    """Process a query with Server-Sent Events streaming.
    
    Uses MCPClientPool to get a per-user client for token isolation.
    Returns events as they happen: session, tool_call, tool_result, response, error, done.
    """
    pool: MCPClientPool = app.state.client_pool
    access_token = None
    
    # Get user's OAuth token if authenticated
    if request.auth_session_id:
        access_token = await auth.get_valid_access_token(request.auth_session_id)
    
    # Get or create client for this user
    client = await pool.get_client(request.auth_session_id, access_token)
    
    async def event_generator():
        try:
            async for event in client.process_query_stream(
                request.query, request.session_id
            ):
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await pool.release_client(request.auth_session_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@app.post("/sessions")
async def create_session():
    """Create a new conversation session."""
    pool: MCPClientPool = app.state.client_pool
    client = await pool.get_client(None, None)
    session_id = client.create_session()
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active session IDs."""
    pool: MCPClientPool = app.state.client_pool
    client = await pool.get_client(None, None)
    sessions = client.list_sessions()
    return {"sessions": sessions}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get messages for a specific session."""
    pool: MCPClientPool = app.state.client_pool
    client = await pool.get_client(None, None)
    messages = client.get_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    pool: MCPClientPool = app.state.client_pool
    client = await pool.get_client(None, None)
    deleted = client.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# =============================================================================
# OAUTH AUTHENTICATION ENDPOINTS
# =============================================================================

@app.get("/auth/salla/url")
async def get_auth_url():
    """Get the Salla OAuth authorization URL.
    
    Returns the URL to redirect the user to for Salla authorization.
    Includes a state parameter for CSRF protection.
    """
    if not settings.salla_client_id:
        raise HTTPException(
            status_code=500,
            detail="Salla OAuth not configured. Set SALLA_CLIENT_ID in environment."
        )
    
    state = auth.generate_state()
    await auth.store_state(state)
    auth_url = auth.generate_auth_url(state)
    
    return {"auth_url": auth_url, "state": state}


@app.post("/auth/salla/callback")
async def oauth_callback(request: OAuthCallbackRequest):
    """Handle OAuth callback from Salla.
    
    Exchanges the authorization code for access and refresh tokens.
    Validates CSRF state parameter for security.
    Returns merchant info on success.
    """
    # CSRF state validation (enabled for production)
    if request.state:
        valid_state = await auth.validate_state(request.state)
        if not valid_state:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    
    try:
        # Exchange code for tokens
        tokens = await auth.exchange_code_for_tokens(request.code)
        
        # Get merchant info
        access_token = tokens.get("access_token")
        merchant_info = {}
        if access_token:
            merchant_info = await auth.get_merchant_info(access_token)
        
        # Generate a session ID for this authenticated user
        session_id = str(uuid.uuid4())
        
        # Store tokens using repository
        await auth.store_tokens(session_id, tokens, merchant_info)
        
        return {
            "success": True,
            "session_id": session_id,
            "merchant_info": {
                "name": merchant_info.get("name", "Merchant"),
                "store_name": merchant_info.get("name", "My Store"),
                "domain": merchant_info.get("domain", ""),
                "email": merchant_info.get("email", ""),
            }
        }
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/status")
async def auth_status():
    """Check authentication status.
    
    In production, use auth_session_id from request to check status.
    """
    return {
        "authenticated": False,
        "merchant_info": None,
        "message": "Use session_id from callback to track authentication"
    }


@app.post("/auth/logout")
async def logout():
    """Logout and clear session."""
    return {"success": True}


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "src.agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )