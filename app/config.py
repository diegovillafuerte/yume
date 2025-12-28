"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "change-me-in-production"
    app_base_url: str = "http://localhost:8000"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/yume"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Meta WhatsApp
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = "yume-webhook-token"
    meta_access_token: str = ""  # For sending messages
    meta_api_version: str = "v18.0"

    # OpenAI
    openai_api_key: str = ""

    # Anthropic (legacy, kept for reference)
    anthropic_api_key: str = ""

    # Observability (optional)
    sentry_dsn: str = ""

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
