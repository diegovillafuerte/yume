"""Message model - represents individual messages in a conversation."""

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class MessageDirection(str, Enum):
    """Message direction enum."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageSenderType(str, Enum):
    """Message sender type enum."""

    END_CUSTOMER = "end_customer"
    AI = "ai"
    YUME_USER = "yume_user"
    # Backwards compatibility aliases
    CUSTOMER = "end_customer"  # Deprecated, use END_CUSTOMER
    STAFF = "yume_user"  # Deprecated, use YUME_USER


class MessageContentType(str, Enum):
    """Message content type enum."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TEMPLATE = "template"


class Message(Base, UUIDMixin, TimestampMixin):
    """Individual messages in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_message_whatsapp_id", "whatsapp_message_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )

    direction: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    content_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MessageContentType.TEXT.value,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Message body
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    whatsapp_message_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        """String representation."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, direction='{self.direction}', sender_type='{self.sender_type}', content='{content_preview}')>"
