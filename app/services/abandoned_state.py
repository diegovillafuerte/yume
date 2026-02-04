"""Abandoned state pattern implementation.

This module provides centralized handling for abandoned conversation sessions
across all flow types (customer flows, staff onboarding, business onboarding).

A session is considered "abandoned" if:
1. It's still active (not completed/cancelled)
2. Last message was more than TIMEOUT_MINUTES ago

When abandoned:
- The current state is saved to collected_data['last_active_state']
- The state is set to 'abandoned'
- When the user returns, the session is resumed from the saved state
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol, TypeVar, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default timeout for all session types
DEFAULT_TIMEOUT_MINUTES = 30


@runtime_checkable
class SessionProtocol(Protocol):
    """Protocol for session models that support abandoned state."""

    id: any
    state: str
    is_active: bool
    last_message_at: datetime
    collected_data: dict


T = TypeVar("T", bound=SessionProtocol)


def is_terminal_state(state: str) -> bool:
    """Check if a state is terminal (cannot be abandoned).

    Args:
        state: Current state string

    Returns:
        True if the state is terminal
    """
    terminal_states = {
        # Customer flow terminal states
        "confirmed",
        "cancelled",
        "submitted",
        "inquiry_answered",
        "abandoned",
        # Onboarding terminal states
        "completed",
    }
    return state.lower() in terminal_states


def should_mark_abandoned(
    session: SessionProtocol,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
) -> bool:
    """Check if a session should be marked as abandoned.

    Args:
        session: Session to check
        timeout_minutes: Timeout threshold in minutes

    Returns:
        True if the session should be marked abandoned
    """
    if not session.is_active:
        return False

    if is_terminal_state(session.state):
        return False

    if session.state == "abandoned":
        return False

    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    # Handle timezone-naive datetimes
    last_message = session.last_message_at
    if last_message.tzinfo is None:
        last_message = last_message.replace(tzinfo=timezone.utc)

    return last_message < timeout_threshold


def mark_as_abandoned(session: SessionProtocol) -> None:
    """Mark a session as abandoned, preserving current state for resumption.

    Args:
        session: Session to mark as abandoned
    """
    collected = dict(session.collected_data or {})
    collected["last_active_state"] = session.state
    collected["abandoned_at"] = datetime.now(timezone.utc).isoformat()

    session.collected_data = collected
    session.state = "abandoned"

    logger.info(
        f"Marked session {session.id} as abandoned, "
        f"last state: {collected['last_active_state']}"
    )


def resume_from_abandoned(session: SessionProtocol) -> str | None:
    """Resume an abandoned session, returning a welcome back message.

    Args:
        session: Session to resume

    Returns:
        Welcome back message, or None if not an abandoned session
    """
    if session.state != "abandoned":
        return None

    collected = dict(session.collected_data or {})
    last_state = collected.pop("last_active_state", None)
    collected.pop("abandoned_at", None)

    if last_state:
        session.state = last_state
        session.collected_data = collected
        session.last_message_at = datetime.now(timezone.utc)

        logger.info(f"Resumed session {session.id} from state: {last_state}")

        return "¡Bienvenido de vuelta! Continuemos donde nos quedamos..."

    # No saved state, reset to initiated
    session.state = "initiated"
    session.collected_data = collected
    session.last_message_at = datetime.now(timezone.utc)

    return "¡Hola de nuevo! ¿En qué puedo ayudarte?"


async def check_and_mark_abandoned_sessions(
    db: AsyncSession,
    session_model: type,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
) -> int:
    """Check for and mark abandoned sessions of a specific type.

    Args:
        db: Database session
        session_model: SQLAlchemy model class (e.g., CustomerFlowSession)
        timeout_minutes: Timeout threshold in minutes

    Returns:
        Number of sessions marked as abandoned
    """
    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    # Find active sessions that have timed out
    result = await db.execute(
        select(session_model).where(
            session_model.is_active == True,
            session_model.last_message_at < timeout_threshold,
        )
    )
    sessions = result.scalars().all()

    count = 0
    for session in sessions:
        if should_mark_abandoned(session, timeout_minutes):
            mark_as_abandoned(session)
            count += 1

    if count > 0:
        await db.flush()
        logger.info(f"Marked {count} {session_model.__name__} session(s) as abandoned")

    return count


def get_time_since_last_message(session: SessionProtocol) -> timedelta:
    """Get time elapsed since last message in a session.

    Args:
        session: Session to check

    Returns:
        Timedelta since last message
    """
    last_message = session.last_message_at
    if last_message.tzinfo is None:
        last_message = last_message.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - last_message


def get_resume_context(session: SessionProtocol) -> dict:
    """Get context information for resuming an abandoned session.

    Args:
        session: Session to get context for

    Returns:
        Dict with resume context information
    """
    collected = session.collected_data or {}

    return {
        "was_abandoned": session.state == "abandoned",
        "last_active_state": collected.get("last_active_state"),
        "abandoned_at": collected.get("abandoned_at"),
        "time_since_abandoned": None,  # Calculate if needed
    }
