"""Dependency injection container for repository instances.

This module provides factory functions for all repositories.
To switch storage backends (e.g., to Redis), simply change the
implementation returned by each function.

Example:
    # Switch from in-memory to Redis:
    def get_token_repository() -> TokenRepository:
        return RedisTokenRepository(redis_client)
"""

from ..repositories import (
    TokenRepository,
    StateRepository,
    RateLimitRepository,
    ConversationRepository,
    InMemoryTokenRepository,
    InMemoryStateRepository,
    InMemoryRateLimitRepository,
    InMemoryConversationRepository,
    SQLAlchemyTokenRepository,
    SQLAlchemyConversationRepository,
    SQLAlchemyUserRepository,
    UserRepository,
)


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================
# We use singletons to share state across the application.
# For Redis/DB backends, you'd create the connection here.

_token_repo: TokenRepository | None = None
_state_repo: StateRepository | None = None
_rate_limit_repo: RateLimitRepository | None = None
_conversation_repo: ConversationRepository | None = None
_user_repo: UserRepository | None = None


# =============================================================================
# CONFIGURE YOUR BACKENDS HERE
# =============================================================================
# Change these to Redis/PostgreSQL implementations when ready.
# The rest of the application uses these functions via dependency injection.


def get_token_repository() -> TokenRepository:
    """Get the token repository instance.

    Returns:
        TokenRepository for storing OAuth tokens.
    """
    global _token_repo
    if _token_repo is None:
        _token_repo = SQLAlchemyTokenRepository()
    return _token_repo


def get_state_repository() -> StateRepository:
    """Get the state repository instance.

    Returns:
        StateRepository for CSRF state parameters.
    """
    global _state_repo
    if _state_repo is None:
        _state_repo = InMemoryStateRepository()
    return _state_repo


def get_rate_limit_repository() -> RateLimitRepository:
    """Get the rate limit repository instance.

    Returns:
        RateLimitRepository for rate limiting.
    """
    global _rate_limit_repo
    if _rate_limit_repo is None:
        _rate_limit_repo = InMemoryRateLimitRepository()
    return _rate_limit_repo


def get_conversation_repository() -> ConversationRepository:
    """Get the conversation repository instance.

    Returns:
        ConversationRepository for storing chat sessions.
    """
    global _conversation_repo
    if _conversation_repo is None:
        _conversation_repo = SQLAlchemyConversationRepository()
    return _conversation_repo


def get_user_repository() -> UserRepository:
    """Get the user repository instance.

    Returns:
        UserRepository for managing user records.
    """
    global _user_repo
    if _user_repo is None:
        _user_repo = SQLAlchemyUserRepository()
    return _user_repo
