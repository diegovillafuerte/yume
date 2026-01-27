"""Spot model - represents a physical service station (chair, table, bed)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.location import Location
    from app.models.service_type import ServiceType
    from app.models.yume_user import YumeUser


class Spot(Base, UUIDMixin, TimestampMixin):
    """A physical service station within a location (chair, table, bed, etc.)."""

    __tablename__ = "spots"
    __table_args__ = (
        UniqueConstraint("location_id", "name", name="uq_spot_location_name"),
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Silla 1", "Mesa 2"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="spots")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="spot"
    )
    # YumeUsers assigned to this spot as their default
    yume_users: Mapped[list["YumeUser"]] = relationship("YumeUser", back_populates="default_spot")
    # Services that can be performed at this spot
    service_types: Mapped[list["ServiceType"]] = relationship(
        "ServiceType",
        secondary="spot_service_types",
        back_populates="spots",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Spot(id={self.id}, name='{self.name}', location_id={self.location_id})>"
