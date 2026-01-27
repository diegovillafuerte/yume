"""Conversation model - represents a WhatsApp conversation thread."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.end_customer import EndCustomer
    from app.models.message import Message
    from app.models.organization import Organization


class ConversationStatus(str, Enum):
    """Conversation status enum."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    HANDED_OFF = "handed_off"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """A WhatsApp conversation thread."""

    __tablename__ = "conversations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    end_customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("end_customers.id", ondelete="CASCADE"), nullable=False
    )
    whatsapp_conversation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Meta's ID

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ConversationStatus.ACTIVE.value,
    )
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # AI conversation state

    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="conversations"
    )
    end_customer: Mapped["EndCustomer"] = relationship("EndCustomer", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Conversation(id={self.id}, status='{self.status}', last_message_at={self.last_message_at})>"
