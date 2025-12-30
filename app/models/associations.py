"""Association tables for many-to-many relationships."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

# Association table: which services can be performed at which spots
spot_service_types = Table(
    "spot_service_types",
    Base.metadata,
    Column(
        "spot_id",
        UUID(as_uuid=True),
        ForeignKey("spots.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "service_type_id",
        UUID(as_uuid=True),
        ForeignKey("service_types.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
)

# Association table: which services each staff member can perform
staff_service_types = Table(
    "staff_service_types",
    Base.metadata,
    Column(
        "staff_id",
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "service_type_id",
        UUID(as_uuid=True),
        ForeignKey("service_types.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
)
