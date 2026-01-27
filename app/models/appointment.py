"""Appointment model - represents a scheduled service event."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.end_customer import EndCustomer
    from app.models.location import Location
    from app.models.organization import Organization
    from app.models.service_type import ServiceType
    from app.models.spot import Spot
    from app.models.yume_user import YumeUser


class AppointmentStatus(str, Enum):
    """Appointment status enum."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentSource(str, Enum):
    """Appointment source enum."""

    WHATSAPP = "whatsapp"
    WEB = "web"
    MANUAL = "manual"
    WALK_IN = "walk_in"


class Appointment(Base, UUIDMixin, TimestampMixin):
    """A scheduled service event."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "scheduled_start < scheduled_end", name="check_appointment_start_before_end"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    end_customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("end_customers.id", ondelete="CASCADE"), nullable=False
    )
    yume_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("yume_users.id", ondelete="SET NULL"),
        nullable=True,  # null = any available
    )
    service_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_types.id", ondelete="CASCADE"), nullable=False
    )
    spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL"), nullable=True
    )

    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AppointmentStatus.PENDING.value,
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AppointmentSource.WHATSAPP.value,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="appointments"
    )
    location: Mapped["Location"] = relationship("Location", back_populates="appointments")
    end_customer: Mapped["EndCustomer"] = relationship("EndCustomer", back_populates="appointments")
    yume_user: Mapped["YumeUser | None"] = relationship(
        "YumeUser", back_populates="appointments", foreign_keys=[yume_user_id]
    )
    service_type: Mapped["ServiceType"] = relationship(
        "ServiceType", back_populates="appointments"
    )
    spot: Mapped["Spot | None"] = relationship("Spot", back_populates="appointments")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Appointment(id={self.id}, status='{self.status}', scheduled_start={self.scheduled_start})>"
