"""Location model - represents a physical location of the business."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.organization import Organization
    from app.models.spot import Spot
    from app.models.staff import Staff


class Location(Base, UUIDMixin, TimestampMixin):
    """Physical location - supports multi-location later."""

    __tablename__ = "locations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    business_hours: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # {mon: {open: "10:00", close: "20:00"}, ...}

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="locations")
    staff: Mapped[list["Staff"]] = relationship("Staff", back_populates="location")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="location"
    )
    spots: Mapped[list["Spot"]] = relationship(
        "Spot", back_populates="location", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Location(id={self.id}, name='{self.name}', is_primary={self.is_primary})>"
