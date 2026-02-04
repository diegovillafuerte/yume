"""EndCustomer model - represents end consumers who book appointments."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.conversation import Conversation
    from app.models.organization import Organization


class EndCustomer(Base, UUIDMixin, TimestampMixin):
    """End consumers who book appointments - created with minimal data initially.

    Customer profiles are incremental - we learn more about them over time.
    The phone_number is the primary cross-business identifier.

    Profile Data Structure (stored in profile_data JSONB):
    {
        "preferred_times": ["morning", "afternoon"],  # Preferred appointment times
        "preferred_days": ["friday", "saturday"],     # Preferred days of week
        "last_services": ["Corte", "Tinte"],          # Recent services used
        "communication_preference": "whatsapp",       # Preferred contact method
        "birthday": "1990-05-15",                     # Optional
        "language": "es-MX",                          # Language preference
    }
    """

    __tablename__ = "end_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone_number", name="uq_end_customer_org_phone"),
        Index("ix_end_customer_phone_number", "phone_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Primary identifier - used for cross-business lookup
    name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Learned over time from conversations
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Business owner's notes
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Profile fields for returning customer experience
    name_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When customer confirmed their name (vs auto-detected)
    profile_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # Extended profile (preferences, history summary)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="end_customers")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="end_customer", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="end_customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        name_display = self.name if self.name else "Unknown"
        return f"<EndCustomer(id={self.id}, name='{name_display}', phone='{self.phone_number}')>"
