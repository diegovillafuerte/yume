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

    @property
    def async_database_url(self) -> str:
        """Get database URL with asyncpg driver.

        Render/Railway provide postgresql:// but SQLAlchemy async needs postgresql+asyncpg://
        This property ensures the correct driver is always used.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""  # Format: whatsapp:+14155238886

    # Meta WhatsApp (legacy - kept for reference)
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = "yume-webhook-token"
    meta_access_token: str = ""
    meta_api_version: str = "v18.0"

    # OpenAI
    openai_api_key: str = ""

    # Anthropic (legacy, kept for reference)
    anthropic_api_key: str = ""

    # Observability (optional)
    sentry_dsn: str = ""

    # JWT Authentication
    jwt_secret_key: str = "change-me-jwt-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Magic Link
    magic_link_expire_minutes: int = 15
    frontend_url: str = "http://localhost:3000"

    # Admin
    admin_master_password: str = ""  # MASTER_PASS - Required for admin access

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
