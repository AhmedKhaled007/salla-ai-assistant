"""FastAPI middleware configuration."""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware


from agent.core import settings, get_rate_limit_repository

_rate_limit_repo = get_rate_limit_repository()


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware using RateLimitRepository."""
    # Skip rate limiting if disabled
    if not settings.rate_limit_enabled:
        return await call_next(request)

    # Get client identity (IP address)
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit key based on IP
    key = f"rate_limit:{client_ip}"

    # Check limit
    repo = _rate_limit_repo
    allowed = await repo.check_and_increment(
        key,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )

    if not allowed:
        return Response(
            content="Rate limit exceeded",
            status_code=429
        )

    response = await call_next(request)

    remaining = await repo.get_remaining(
        key,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )

    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = str(settings.rate_limit_window)

    return response


def setup_cors(app):
    """Configure CORS middleware for the application."""
    origins = [origin.strip() for origin in settings.allowed_origins.split(",")]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Auth-Session-Id", "X-Requested-With"],
    )
