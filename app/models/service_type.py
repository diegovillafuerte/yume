"""ServiceType model - represents services offered by the business."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.organization import Organization
    from app.models.spot import Spot
    from app.models.yume_user import YumeUser


class ServiceType(Base, UUIDMixin, TimestampMixin):
    """What the business offers (e.g., 'Corte de cabello')."""

    __tablename__ = "service_types"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # 15000 = $150.00 MXN
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # e.g., {requires_deposit: false}

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="service_types"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="service_type"
    )
    # Spots that can perform this service
    spots: Mapped[list["Spot"]] = relationship(
        "Spot",
        secondary="spot_service_types",
        back_populates="service_types",
    )
    # YumeUsers that can perform this service
    yume_users: Mapped[list["YumeUser"]] = relationship(
        "YumeUser",
        secondary="yume_user_service_types",
        back_populates="service_types",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ServiceType(id={self.id}, name='{self.name}', price_cents={self.price_cents})>"
