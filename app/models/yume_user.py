"""YumeUser model - represents employees and owners who use Yume."""

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.availability import Availability
    from app.models.location import Location
    from app.models.organization import Organization
    from app.models.service_type import ServiceType
    from app.models.spot import Spot


class YumeUserRole(str, Enum):
    """Yume user role enum."""

    OWNER = "owner"
    EMPLOYEE = "employee"


class YumeUser(Base, UUIDMixin, TimestampMixin):
    """People who provide services - also users who can interact via WhatsApp."""

    __tablename__ = "yume_users"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone_number", name="uq_yume_user_org_phone"),
        Index("ix_yume_user_phone_number", "phone_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    default_spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Their personal WhatsApp - used to identify them as yume_user
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=YumeUserRole.EMPLOYEE.value
    )
    permissions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # {can_view_schedule: true, can_book: true, can_cancel: true, ...}
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="yume_users")
    location: Mapped["Location | None"] = relationship("Location", back_populates="yume_users")
    default_spot: Mapped["Spot | None"] = relationship("Spot", back_populates="yume_users")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="yume_user", foreign_keys="Appointment.yume_user_id"
    )
    availability: Mapped[list["Availability"]] = relationship(
        "Availability", back_populates="yume_user", cascade="all, delete-orphan"
    )
    # Services this yume_user can perform
    service_types: Mapped[list["ServiceType"]] = relationship(
        "ServiceType",
        secondary="yume_user_service_types",
        back_populates="yume_users",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<YumeUser(id={self.id}, name='{self.name}', role='{self.role}', phone='{self.phone_number}')>"
