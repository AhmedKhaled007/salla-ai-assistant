"""API layer for FastAPI application.

This package contains the API router, models, middleware, and dependencies.
"""

from fastapi import APIRouter

from .routes import (
    health,
    query,
    conversation,
    auth,
)

# Consolidated router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(query.router, prefix="/api", tags=["Query"])
api_router.include_router(conversation.router, prefix="/api", tags=["Conversation"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
