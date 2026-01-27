"""EndCustomer model - represents end consumers who book appointments."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.conversation import Conversation
    from app.models.organization import Organization


class EndCustomer(Base, UUIDMixin, TimestampMixin):
    """End consumers who book appointments - created with minimal data initially."""

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
    )  # Primary identifier, may be only data initially
    name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Learned over time
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Business owner's notes
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

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
