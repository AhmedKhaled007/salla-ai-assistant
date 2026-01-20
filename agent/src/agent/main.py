"""Agent Service - FastAPI application for AI-powered Salla assistant."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .core import settings, logger
from .services import MCPClientPool
from .api import api_router
from .api.middleware import rate_limit_middleware, setup_cors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown.

    Handles:
    - MCPClientPool initialization on startup
    - Cleanup of all pooled resources on shutdown
    """
    # Startup
    logger.info("Starting up Salla AI Agent...")

    # Initialize connection pool
    pool = MCPClientPool(
        transport=settings.mcp_transport,
        server_url=settings.mcp_server_url,
        server_script_path=settings.server_script_path
    )

    # Store pool in app state immediately so cleanup runs even if init fails
    app.state.pool = pool

    try:
        await pool.initialize()

        # Check connection (warn but don't fail startup)
        if not await pool.ping():
            logger.warning("Default MCP client failed to connect to server")
        else:
            logger.info("Successfully connected to MCP server")

    except Exception as e:
        logger.error(f"Failed to initialize pool: {e}")
        # Allow running in degraded mode

    yield

    # Shutdown
    logger.info("Shutting down Salla AI Agent...")
    if hasattr(app.state, "pool"):
        await app.state.pool.cleanup_all()


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
