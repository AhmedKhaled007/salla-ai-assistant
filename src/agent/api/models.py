"""Pydantic models for API request/response validation."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from ..core import settings


class QueryRequest(BaseModel):
    """Request model for query endpoint with validation."""
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=settings.max_query_length,
        description="The user's query text"
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID to continue existing conversation"
    )


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code from Salla")
    state: str | None = Field(default=None, description="CSRF state parameter")
