"""ExecutionTracer service - captures execution traces for debugging.

This service provides a lightweight way to capture detailed execution data
during message processing, enabling comprehensive debugging through the
admin playground UI.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExecutionTrace, ExecutionTraceType

logger = logging.getLogger(__name__)


class ExecutionTracer:
    """Captures execution traces for a single message exchange.

    Usage:
        tracer = ExecutionTracer(db, organization_id)

        # Trace a step
        with tracer.trace_step(ExecutionTraceType.LLM_CALL) as step:
            step.set_input({"prompt": "...", "messages": [...]})
            result = await call_llm(...)
            step.set_output({"response": result})
            step.set_metadata({"tokens": 100})

        # Save all traces at the end
        await tracer.save_traces(message_id=msg.id, conversation_id=conv.id)
    """

    def __init__(self, db: AsyncSession, organization_id: UUID):
        """Initialize the tracer.

        Args:
            db: Database session
            organization_id: Organization ID for scoping
        """
        self.db = db
        self.organization_id = organization_id
        self.exchange_id = uuid.uuid4()
        self.sequence = 0
        self.traces: list[dict[str, Any]] = []

    def trace_step(self, trace_type: ExecutionTraceType) -> "TraceStep":
        """Create a trace step context manager.

        Args:
            trace_type: Type of execution step

        Returns:
            TraceStep context manager
        """
        return TraceStep(self, trace_type)

    def _add_trace(
        self,
        trace_type: ExecutionTraceType,
        started_at: datetime,
        completed_at: datetime,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        metadata: dict[str, Any],
        is_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Add a trace record to the pending list.

        Args:
            trace_type: Type of execution step
            started_at: When the step started
            completed_at: When the step completed
            input_data: Input to this step
            output_data: Output from this step
            metadata: Additional metadata (tokens, etc.)
            is_error: Whether this step errored
            error_message: Error message if errored
        """
        latency_ms = int((completed_at - started_at).total_seconds() * 1000)

        self.traces.append({
            "exchange_id": self.exchange_id,
            "organization_id": self.organization_id,
            "trace_type": trace_type.value,
            "sequence_number": self.sequence,
            "started_at": started_at,
            "completed_at": completed_at,
            "latency_ms": latency_ms,
            "input_data": input_data,
            "output_data": output_data,
            "trace_metadata": metadata,
            "is_error": is_error,
            "error_message": error_message,
        })

        self.sequence += 1

    async def save_traces(
        self,
        message_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> list[ExecutionTrace]:
        """Persist all collected traces to the database.

        Args:
            message_id: Optional message ID to associate with traces
            conversation_id: Optional conversation ID to associate with traces

        Returns:
            List of created ExecutionTrace objects
        """
        if not self.traces:
            return []

        created_traces = []
        for trace_data in self.traces:
            trace = ExecutionTrace(
                exchange_id=trace_data["exchange_id"],
                message_id=message_id,
                conversation_id=conversation_id,
                organization_id=trace_data["organization_id"],
                trace_type=trace_data["trace_type"],
                sequence_number=trace_data["sequence_number"],
                started_at=trace_data["started_at"],
                completed_at=trace_data["completed_at"],
                latency_ms=trace_data["latency_ms"],
                input_data=trace_data["input_data"],
                output_data=trace_data["output_data"],
                trace_metadata=trace_data["trace_metadata"],
                is_error=trace_data["is_error"],
                error_message=trace_data["error_message"],
            )
            self.db.add(trace)
            created_traces.append(trace)

        await self.db.flush()

        logger.debug(
            f"Saved {len(created_traces)} traces for exchange {self.exchange_id}"
        )

        return created_traces

    def get_exchange_id(self) -> UUID:
        """Get the exchange ID for this tracer."""
        return self.exchange_id

    def get_total_latency_ms(self) -> int:
        """Get the total latency of all traces."""
        return sum(t["latency_ms"] for t in self.traces)


class TraceStep:
    """Context manager for tracing a single execution step."""

    def __init__(self, tracer: ExecutionTracer, trace_type: ExecutionTraceType):
        """Initialize the trace step.

        Args:
            tracer: Parent tracer
            trace_type: Type of execution step
        """
        self.tracer = tracer
        self.trace_type = trace_type
        self.started_at: datetime | None = None
        self.input_data: dict[str, Any] = {}
        self.output_data: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}
        self.is_error = False
        self.error_message: str | None = None

    def __enter__(self) -> "TraceStep":
        """Start timing the step."""
        self.started_at = datetime.now(timezone.utc)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Complete the step and add to tracer."""
        completed_at = datetime.now(timezone.utc)

        if exc_type is not None:
            self.is_error = True
            self.error_message = str(exc_val)

        self.tracer._add_trace(
            trace_type=self.trace_type,
            started_at=self.started_at,
            completed_at=completed_at,
            input_data=self.input_data,
            output_data=self.output_data,
            metadata=self.metadata,
            is_error=self.is_error,
            error_message=self.error_message,
        )

    def set_input(self, data: dict[str, Any]) -> "TraceStep":
        """Set input data for this step.

        Args:
            data: Input data dictionary

        Returns:
            Self for chaining
        """
        self.input_data = data
        return self

    def set_output(self, data: dict[str, Any]) -> "TraceStep":
        """Set output data for this step.

        Args:
            data: Output data dictionary

        Returns:
            Self for chaining
        """
        self.output_data = data
        return self

    def set_metadata(self, data: dict[str, Any]) -> "TraceStep":
        """Set metadata for this step.

        Args:
            data: Metadata dictionary

        Returns:
            Self for chaining
        """
        self.metadata = data
        return self

    def set_error(self, message: str) -> "TraceStep":
        """Mark this step as an error.

        Args:
            message: Error message

        Returns:
            Self for chaining
        """
        self.is_error = True
        self.error_message = message
        return self


def truncate_for_trace(data: Any, max_length: int = 500) -> Any:
    """Truncate data for storage in traces.

    Useful for truncating long strings like prompts or responses
    to keep trace data manageable.

    Args:
        data: Data to truncate
        max_length: Maximum string length

    Returns:
        Truncated data
    """
    if isinstance(data, str):
        if len(data) > max_length:
            return data[:max_length] + "..."
        return data
    elif isinstance(data, dict):
        return {k: truncate_for_trace(v, max_length) for k, v in data.items()}
    elif isinstance(data, list):
        return [truncate_for_trace(item, max_length) for item in data]
    return data
