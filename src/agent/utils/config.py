from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env",env_file_encoding="utf-8",extra="ignore")

    # LLM Configuration
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_temperature: float = 1

    # MCP Server Configuration
    server_script_path: str = "/home/ahmed/projects/salla-agent/src/mcp_server/main.py"

    # API Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Agent Configuration
    max_iterations: int = 10  # Max tool-calling iterations per query

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    log_file: str | None = None


# Global settings instance
settings = Settings()
