"""API layer for FastAPI application.

This package contains the API router, models, middleware, and dependencies.
"""

from fastapi import APIRouter

from .routes import (
    health,
    query,
    session,
    auth,
)

# Consolidated router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(query.router, prefix="/api", tags=["Query"])
api_router.include_router(session.router, prefix="/api", tags=["Session"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
