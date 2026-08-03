"""Tests for utility functions."""
import pytest
from unittest.mock import MagicMock

from mcp_server.utils import get_salla_client, format_error
from mcp_server.salla_client import SallaClient


class TestGetSallaClient:
    """Tests for get_salla_client utility."""

    def test_extracts_bearer_token(self, mock_context):
        """Test extracting Bearer token from context."""
        client = get_salla_client(mock_context)
        
        assert isinstance(client, SallaClient)
        assert client._access_token == "test_token_123"

    def test_no_auth_header_raises(self, mock_context_no_auth):
        """Test error when no Authorization header."""
        with pytest.raises(ValueError, match="No authorization token found"):
            get_salla_client(mock_context_no_auth)

    def test_invalid_auth_format_raises(self):
        """Test error when Authorization header has wrong format."""
        ctx = MagicMock()
        ctx.request_context.request.headers = {"Authorization": "Basic xyz"}
        
        with pytest.raises(ValueError, match="No authorization token found"):
            get_salla_client(ctx)

    def test_empty_bearer_token_raises(self):
        """Test error when Bearer token is empty."""
        ctx = MagicMock()
        ctx.request_context.request.headers = {"Authorization": "Bearer "}
        
        with pytest.raises(ValueError):
            get_salla_client(ctx)

    def test_case_insensitive_bearer(self):
        """Test Bearer prefix is case insensitive."""
        ctx = MagicMock()
        ctx.request_context.request.headers = {"Authorization": "bearer my-token"}
        
        client = get_salla_client(ctx)
        assert client._access_token == "my-token"


class TestFormatError:
    """Tests for format_error utility."""

    def test_formats_exception(self):
        """Test formatting an exception."""
        error = ValueError("Something went wrong")
        result = format_error(error)
        
        assert result == {"error": "Something went wrong"}

    def test_formats_generic_exception(self):
        """Test formatting a generic exception."""
        error = Exception("Generic error")
        result = format_error(error)
        
        assert result == {"error": "Generic error"}

    def test_formats_runtime_error(self):
        """Test formatting a RuntimeError."""
        error = RuntimeError("Runtime issue")
        result = format_error(error)
        
        assert result == {"error": "Runtime issue"}

    @pytest.mark.parametrize("message", [
        "Simple error",
        "Error with: special chars!",
        "Multi\nline\nerror",
        "",
    ])
    def test_various_error_messages(self, message):
        """Test formatting various error messages."""
        error = Exception(message)
        result = format_error(error)
        
        assert result["error"] == message
