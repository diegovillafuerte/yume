"""AuthToken model - for magic link authentication."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class TokenType(str, Enum):
    """Token type enum."""

    MAGIC_LINK = "magic_link"


class AuthToken(Base, UUIDMixin, TimestampMixin):
    """Authentication tokens for magic link login."""

    __tablename__ = "auth_tokens"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )  # SHA256 hash of the actual token
    token_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TokenType.MAGIC_LINK.value
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Set when token is used

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        """String representation."""
        return f"<AuthToken(id={self.id}, type='{self.token_type}', expires_at={self.expires_at})>"

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return self.expires_at > now and self.used_at is None
