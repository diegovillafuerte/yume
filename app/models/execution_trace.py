"""ExecutionTrace model - stores AI pipeline execution traces for debugging.

This model captures detailed execution data for each message processing step,
enabling comprehensive debugging through the admin playground UI.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class ExecutionTraceType(str, Enum):
    """Types of execution trace steps."""

    MESSAGE_RECEIVED = "message_received"
    ROUTING_DECISION = "routing_decision"
    LLM_CALL = "llm_call"
    TOOL_EXECUTION = "tool_execution"
    RESPONSE_ASSEMBLED = "response_assembled"


class ExecutionTrace(Base, UUIDMixin, TimestampMixin):
    """Stores execution trace data for message processing pipeline.

    Each trace represents a single step in the message processing pipeline.
    Multiple traces with the same exchange_id form a complete processing record.
    """

    __tablename__ = "execution_traces"

    # Exchange grouping - all traces for one message exchange share this ID
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Optional references to related entities
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Organization scoping (required)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Trace type and ordering
    trace_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Timing information
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Execution data (JSONB for flexible structure)
    input_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    output_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Error tracking
    is_error: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="execution_traces",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ExecutionTrace(id={self.id}, exchange_id={self.exchange_id}, "
            f"type='{self.trace_type}', seq={self.sequence_number}, latency={self.latency_ms}ms)>"
        )
