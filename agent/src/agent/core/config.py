"""Application configuration using Pydantic Settings.

All configuration is loaded from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from pathlib import Path


# Get project root (assuming config is at src/agent/core/config.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production", "test"] = "production"
    database_url: str
    # LLM Configuration
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_temperature: float = 1
    llm_max_retries: int = 1  # Max retry attempts for LLM calls
    llm_retry_delay: float = 1.0  # Base delay in seconds (exponential backoff)

    # MCP Server Configuration
    server_script_path: str = str(_PROJECT_ROOT / "src" / "mcp_server" / "main.py")
    mcp_transport: str = "http"  # Transport type: 'stdio' or 'http'
    mcp_server_url: str = "http://localhost:8001/mcp"  # URL for HTTP transport

    # API Server Configuration
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Agent Configuration
    max_iterations: int = 10  # Max tool-calling iterations per query
    max_query_length: int = 10000  # Max characters in query (prevent abuse)
    llm_max_tokens: int | None = 4096
    tool_timeout: float = 30.0  # Timeout in seconds for tool execution

    # CORS Configuration
    allowed_origins: str = "http://localhost:5173"  # Comma-separated origins

    # Rate Limiting Configuration
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60  # Max requests per window
    rate_limit_window: int = 60  # Window size in seconds

    # Salla OAuth Configuration
    salla_client_id: str
    salla_client_secret: str
    salla_redirect_uri: str
    salla_oauth_base_url: str = "https://accounts.salla.sa/oauth2"
    salla_scopes: str = "offline_access"

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: str | None = None  # Optional file path for logging
    conversation_log_dir: str = "conversations"  # Directory for conversation logs


# Global settings instance
settings = Settings()
