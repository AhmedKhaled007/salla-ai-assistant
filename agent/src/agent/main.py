"""Agent Service - FastAPI application for AI-powered Salla assistant."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent.core import settings, logger
from agent.services import MCPClient
from agent.api import api_router
from agent.api.middleware import rate_limit_middleware, setup_cors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown.

    Handles:
    - MCPClient initialization on startup
    - Cleanup of resources on shutdown
    """
    # Startup
    logger.info("Starting up Salla AI Agent...")

    # Initialize single MCP client
    mcp_client = MCPClient(
        transport=settings.mcp_transport,
        server_url=settings.mcp_server_url
    )

    # Store in app state
    app.state.mcp_client = mcp_client

    try:
        # Check connection
        if not await mcp_client.ping():
            logger.warning("MCP client failed to connect to server")
        else:
            logger.info("Successfully connected to MCP server")

    except Exception as e:
        logger.error(f"Failed to initialize pool: {e}")
        # Allow running in degraded mode

    yield

    # Shutdown
    logger.info("Shutting down Salla AI Agent...")
    if hasattr(app.state, "mcp_client"):
        await app.state.mcp_client.cleanup()


app = FastAPI(title="Salla AI Agent API", lifespan=lifespan)

# Add middleware
setup_cors(app)
app.middleware("http")(rate_limit_middleware)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse(content={
        "service": "Salla AI Agent",
        "status": "running",
        "docs_url": "/docs"
    })
