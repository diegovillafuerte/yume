"""FunctionTrace model - stores automatic function call traces for debugging.

This model captures execution traces via the @traced decorator, enabling
comprehensive debugging through the admin logs dashboard.
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class FunctionTraceType(str, Enum):
    """Types of function traces."""

    SERVICE = "service"
    AI_TOOL = "ai_tool"
    EXTERNAL_API = "external_api"


class FunctionTrace(Base, UUIDMixin, TimestampMixin):
    """Stores function call trace data captured by @traced decorator.

    Traces are grouped by correlation_id - all traces from a single request
    (e.g., webhook handler) share the same correlation_id.
    """

    __tablename__ = "function_traces"

    # Grouping - all traces from one request share this ID
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # For nested calls (optional, for future use)
    parent_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Order within correlation
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Function info
    function_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    module_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    trace_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=FunctionTraceType.SERVICE.value,
    )

    # Execution data (JSONB for flexible structure)
    input_summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    output_summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Context
    phone_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Error tracking
    is_error: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    error_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Define indexes
    __table_args__ = (
        Index('ix_func_trace_corr_seq', 'correlation_id', 'sequence_number'),
        Index('ix_func_trace_created', 'created_at'),
        Index('ix_func_trace_phone', 'phone_number'),
        Index('ix_func_trace_org', 'organization_id'),
        Index('ix_func_trace_error', 'is_error'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<FunctionTrace(id={self.id}, corr={self.correlation_id}, "
            f"func='{self.function_name}', seq={self.sequence_number}, "
            f"duration={self.duration_ms}ms, error={self.is_error})>"
        )
