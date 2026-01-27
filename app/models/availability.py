"""Availability model - represents staff availability patterns and exceptions."""

import uuid
from datetime import date, time
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.yume_user import YumeUser


class AvailabilityType(str, Enum):
    """Availability type enum."""

    RECURRING = "recurring"
    EXCEPTION = "exception"


class Availability(Base, UUIDMixin, TimestampMixin):
    """Staff availability patterns and exceptions."""

    __tablename__ = "availability"

    yume_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("yume_users.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    # For recurring: day of week pattern
    day_of_week: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 0=Monday, 6=Sunday
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # For exceptions: specific date range
    exception_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_available: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )  # false = blocked off

    # Relationships
    yume_user: Mapped["YumeUser"] = relationship("YumeUser", back_populates="availability")

    def __repr__(self) -> str:
        """String representation."""
        if self.type == AvailabilityType.RECURRING:
            return f"<Availability(id={self.id}, type='recurring', day_of_week={self.day_of_week}, {self.start_time}-{self.end_time})>"
        else:
            return f"<Availability(id={self.id}, type='exception', date={self.exception_date}, is_available={self.is_available})>"
