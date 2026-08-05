"""Agent Service - FastAPI application for AI-powered Salla assistant."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent.core import settings, logger
from agent.core.observability import phoenix_observability
from agent.services import MCPClient
from agent.api import api_router
from agent.api.middleware import rate_limit_middleware, setup_cors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown.

    Handles:
    - MCPClient initialization on startup
    - Query-scoped MCP connection factory registration
    """
    # Startup
    logger.info("Starting up Salla AI Agent...")
    app.state.mcp_client = MCPClient(server_url=settings.mcp_server_url)

    with phoenix_observability(settings) as tracer_provider:
        app.state.tracer_provider = tracer_provider
        yield


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
