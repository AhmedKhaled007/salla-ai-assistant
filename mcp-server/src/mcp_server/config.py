"""Configuration for Salla MCP Server."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Salla API configuration settings."""

    # Salla API credentials
    salla_access_token: str = ""
    salla_api_base_url: str = "https://api.salla.dev/admin/v2"

    # API settings
    api_timeout: int = 30
    api_max_retries: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
