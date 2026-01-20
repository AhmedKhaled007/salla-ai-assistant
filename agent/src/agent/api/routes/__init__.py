from .health import router as health_router
from .query import router as query_router
from .conversation import router as conversation_router
from .auth import router as auth_router

__all__ = ["health_router", "query_router", "conversation_router", "auth_router"]
