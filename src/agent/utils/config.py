from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from pathlib import Path


# Get project root (assuming config is at src/agent/utils/config.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env",env_file_encoding="utf-8",extra="ignore")

    # LLM Configuration
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_temperature: float = 1
    llm_max_retries: int = 3  # Max retry attempts for LLM calls
    llm_retry_delay: float = 1.0  # Base delay in seconds (exponential backoff)

    # MCP Server Configuration (relative to project root, or set SERVER_SCRIPT_PATH env var)
    server_script_path: str = str(_PROJECT_ROOT / "src" / "mcp_server" / "main.py")

    # API Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Agent Configuration
    max_iterations: int = 10  # Max tool-calling iterations per query
    max_query_length: int = 10000  # Max characters in query (prevent abuse)
    llm_max_tokens: int | None = None  # Max tokens for LLM response (None = model default)

    # CORS Configuration
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"  # Comma-separated origins

    # Rate Limiting Configuration
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60  # Max requests per window
    rate_limit_window: int = 60  # Window size in seconds

    # Authentication Configuration
    api_key_enabled: bool = False  # Enable API key auth (set to True in production)
    api_key: str | None = None  # Set API_KEY env var to enable authentication

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    log_file: str | None = None


# Global settings instance
settings = Settings()
