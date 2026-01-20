"""Repository layer for data access.

This package contains abstract repository interfaces and their implementations.
Each file contains the abstract base class and all implementations for that entity.
"""

from .token import TokenRepository, InMemoryTokenRepository, SQLAlchemyTokenRepository
from .state import StateRepository, InMemoryStateRepository
from .rate_limit import RateLimitRepository, InMemoryRateLimitRepository
from .conversation import ConversationRepository, InMemoryConversationRepository, SQLAlchemyConversationRepository
from .user import UserRepository, SQLAlchemyUserRepository

__all__ = [
    # Abstract base classes
    "TokenRepository",
    "StateRepository",
    "RateLimitRepository",
    "ConversationRepository",
    "UserRepository",
    # In-memory implementations
    "InMemoryTokenRepository",
    "InMemoryStateRepository",
    "InMemoryRateLimitRepository",
    "InMemoryConversationRepository",
    # SQLAlchemy implementations
    "SQLAlchemyTokenRepository",
    "SQLAlchemyConversationRepository",
    "SQLAlchemyUserRepository",
]
