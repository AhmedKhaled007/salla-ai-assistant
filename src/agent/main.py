from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any
from contextlib import asynccontextmanager
import asyncio
import json

from .mcp_client import MCPClient
from .utils import settings, logger
from . import auth


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

import signal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown.
    
    Handles:
    - MCP server connection on startup
    - Graceful shutdown on SIGTERM/SIGINT
    - Cleanup of resources
    """
    client = MCPClient()
    shutdown_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal_handler)
    
    try:
        logger.info("Starting agent service...")
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise RuntimeError("Failed to connect to MCP server")
        app.state.client = client
        logger.info("Agent service started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during lifespan: {e}")
        raise RuntimeError(f"Startup failed: {e}") from e
    finally:
        # Graceful shutdown
        logger.info("Shutting down agent service...")
        await client.cleanup()
        logger.info("Agent service shutdown complete")


app = FastAPI(title="MCP Client API", lifespan=lifespan)


# Add CORS middleware with configurable origins
# Set ALLOWED_ORIGINS env var for production (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Simple in-memory rate limiting
from collections import defaultdict
import time

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Rate limiting middleware based on client IP."""
    if not settings.rate_limit_enabled:
        return await call_next(request)
    
    # Get client IP (use X-Forwarded-For if behind proxy)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    now = time.time()
    window_start = now - settings.rate_limit_window
    
    # Clean old entries and add current request
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]
    
    if len(_rate_limit_store[client_ip]) >= settings.rate_limit_requests:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
            headers={"Retry-After": str(settings.rate_limit_window)}
        )
    
    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


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
        description="Optional session ID to continue existing conversation"
    )


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer probes.
    
    Performs live ping to MCP server to verify connectivity.
    Returns MCP connection status, LLM availability, and service info.
    """
    # Perform live ping check
    mcp_responsive = await app.state.client.ping()
    
    return {
        "status": "healthy" if mcp_responsive else "degraded",
        "mcp_connected": app.state.client.is_connected,
        "mcp_responsive": mcp_responsive,
        "llm_model": settings.llm_model,
        "active_sessions": len(app.state.client.list_sessions()),
    }


@app.post("/query", dependencies=[Depends(verify_api_key)])
async def process_query(request: QueryRequest):
    """Process a query and return the response.
    
    If session_id is provided, continues the existing conversation.
    Otherwise, starts a new session.
    Requires X-API-Key header if authentication is enabled.
    """
    try:
        session_id, messages = await app.state.client.process_query(
            request.query, request.session_id
        )
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream", dependencies=[Depends(verify_api_key)])
async def process_query_stream(request: QueryRequest):
    """Process a query with Server-Sent Events streaming.
    
    Returns events as they happen:
    - session: Initial session ID
    - tool_call: When a tool is being called
    - tool_result: Result from a tool call
    - response: Final assistant response
    - error: If an error occurs
    - done: When processing is complete
    
    Requires X-API-Key header if authentication is enabled.
    """
    async def event_generator():
        async for event in app.state.client.process_query_stream(
            request.query, request.session_id
        ):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        tools = await app.state.client.get_mcp_tools()
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


# Session Management Endpoints

@app.post("/sessions")
async def create_session():
    """Create a new conversation session."""
    session_id = app.state.client.create_session()
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active session IDs."""
    sessions = app.state.client.list_sessions()
    return {"sessions": sessions}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get messages for a specific session."""
    messages = app.state.client.get_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    deleted = app.state.client.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# ============ OAuth Authentication Endpoints ============

class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code from Salla")
    state: str | None = Field(default=None, description="CSRF state parameter")


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
    auth.store_state(state)
    auth_url = auth.generate_auth_url(state)
    
    return {"auth_url": auth_url, "state": state}


@app.post("/auth/salla/callback")
async def oauth_callback(request: OAuthCallbackRequest):
    """Handle OAuth callback from Salla.
    
    Exchanges the authorization code for access and refresh tokens.
    Returns merchant info on success.
    """
    # Note: State validation is optional for demo but recommended for production
    # if request.state and not auth.validate_state(request.state):
    #     raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    try:
        # Exchange code for tokens
        tokens = await auth.exchange_code_for_tokens(request.code)
        
        # Get merchant info
        access_token = tokens.get("access_token")
        merchant_info = {}
        if access_token:
            merchant_info = await auth.get_merchant_info(access_token)
        
        # Generate a session ID for this authenticated user
        import uuid
        session_id = str(uuid.uuid4())
        
        # Store tokens
        auth.store_tokens(session_id, tokens, merchant_info)
        
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
    
    For demo purposes, this checks if any session is authenticated.
    In production, you'd use cookies or Bearer tokens to identify the session.
    """
    # For demo: check localStorage session on frontend
    # Real implementation would use HTTP-only cookies or session headers
    return {
        "authenticated": False,
        "merchant_info": None,
        "message": "Use session_id from callback to track authentication"
    }


@app.post("/auth/logout")
async def logout():
    """Logout and clear session.
    
    In production, this would invalidate the session cookie/token.
    """
    # For demo: frontend handles logout by clearing localStorage
    return {"success": True}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "src.agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )