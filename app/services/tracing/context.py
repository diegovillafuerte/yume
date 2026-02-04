"""Trace context management using contextvars.

Context variables automatically propagate through async calls, so any function
decorated with @traced will automatically be grouped under the same correlation_id.
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.function_trace import FunctionTrace


# Context variables - automatically propagate through async calls
_correlation_id: ContextVar[UUID | None] = ContextVar('correlation_id', default=None)
_phone_number: ContextVar[str | None] = ContextVar('phone_number', default=None)
_organization_id: ContextVar[UUID | None] = ContextVar('organization_id', default=None)
_sequence_counter: ContextVar[int] = ContextVar('sequence_counter', default=0)
_pending_traces: ContextVar[list["FunctionTrace"]] = ContextVar('pending_traces', default=None)


def start_trace_context(
    phone_number: str | None = None,
    organization_id: UUID | None = None,
) -> UUID:
    """Initialize trace context at request start. Returns correlation_id.

    Call this at the beginning of a request (e.g., webhook entry) to establish
    a correlation context for all subsequent traced function calls.

    Args:
        phone_number: The phone number of the actor (if known)
        organization_id: The organization context (if known)

    Returns:
        The generated correlation_id for this request
    """
    corr_id = uuid4()
    _correlation_id.set(corr_id)
    _phone_number.set(phone_number)
    _organization_id.set(organization_id)
    _sequence_counter.set(0)
    _pending_traces.set([])
    return corr_id


def get_correlation_id() -> UUID | None:
    """Get the current correlation ID, or None if no trace context."""
    return _correlation_id.get()


def get_phone_number() -> str | None:
    """Get the phone number from the trace context."""
    return _phone_number.get()


def get_organization_id() -> UUID | None:
    """Get the organization ID from the trace context."""
    return _organization_id.get()


def set_organization_id(org_id: UUID | None) -> None:
    """Update the organization ID in the trace context.

    Useful when the org is discovered mid-request (e.g., after routing).
    """
    _organization_id.set(org_id)


def get_next_sequence_number() -> int:
    """Get and increment the sequence counter."""
    seq = _sequence_counter.get()
    _sequence_counter.set(seq + 1)
    return seq


def add_pending_trace(trace: "FunctionTrace") -> None:
    """Add a trace to the pending list for later persistence."""
    traces = _pending_traces.get()
    if traces is not None:
        traces.append(trace)


async def save_pending_traces(db: "AsyncSession") -> int:
    """Persist all pending traces to the database.

    Call this at the end of a request to save all captured traces.

    Args:
        db: The async database session

    Returns:
        Number of traces saved
    """
    traces = _pending_traces.get()
    if not traces:
        return 0

    db.add_all(traces)
    await db.flush()
    count = len(traces)

    # Clear for safety
    _pending_traces.set([])

    return count


def clear_trace_context() -> None:
    """Clear all trace context. Call after saving traces."""
    _correlation_id.set(None)
    _phone_number.set(None)
    _organization_id.set(None)
    _sequence_counter.set(0)
    _pending_traces.set(None)
