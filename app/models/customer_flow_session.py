"""Customer flow session model - tracks end customer conversation flows.

See docs/PROJECT_SPEC.md for the customer flow state machines:

New Booking Flow:
    initiated → collecting_service → collecting_datetime → collecting_staff_preference
    → collecting_personal_info → confirming_summary → confirmed

Modify Booking Flow:
    initiated → identifying_booking → selecting_modification → collecting_new_*
    → confirming_summary → confirmed

Cancel Booking Flow:
    initiated → identifying_booking → confirming_cancellation → cancelled

Rating Flow:
    prompted → collecting_rating → collecting_feedback → submitted

This flow is triggered when end customers interact with a business WhatsApp number
(Case 5 in message routing).
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CustomerFlowType(str, Enum):
    """Type of customer flow being executed."""

    BOOKING = "booking"  # New appointment booking
    MODIFY = "modify"  # Modify existing booking
    CANCEL = "cancel"  # Cancel booking
    RATING = "rating"  # Post-appointment rating
    INQUIRY = "inquiry"  # General questions (stateless, but tracked for analytics)


class CustomerFlowState(str, Enum):
    """Customer flow states - covers all states across all flow types.

    State naming follows the architecture convention:
    - Active states use present progressive: collecting_*, confirming_*
    - Completed states use past tense: confirmed, cancelled, submitted
    """

    # === Common States ===
    INITIATED = "initiated"  # Flow just started
    ABANDONED = "abandoned"  # Timed out, stores last_active_state in collected_data

    # === Booking Flow States ===
    COLLECTING_SERVICE = "collecting_service"  # Asking which service
    COLLECTING_DATETIME = "collecting_datetime"  # Asking when
    COLLECTING_STAFF_PREFERENCE = "collecting_staff_preference"  # Asking who (if multiple staff)
    COLLECTING_PERSONAL_INFO = "collecting_personal_info"  # Asking name (prefilled for returning)
    CONFIRMING_SUMMARY = "confirming_summary"  # Showing summary, asking confirmation
    CONFIRMED = "confirmed"  # Booking created

    # === Modify Flow States ===
    IDENTIFYING_BOOKING = "identifying_booking"  # Which booking to modify/cancel
    SELECTING_MODIFICATION = "selecting_modification"  # What to change
    COLLECTING_NEW_SERVICE = "collecting_new_service"  # New service selection
    COLLECTING_NEW_DATETIME = "collecting_new_datetime"  # New date/time
    COLLECTING_NEW_STAFF = "collecting_new_staff"  # New staff selection

    # === Cancel Flow States ===
    CONFIRMING_CANCELLATION = "confirming_cancellation"  # Are you sure?
    CANCELLED = "cancelled"  # Booking cancelled

    # === Rating Flow States ===
    PROMPTED = "prompted"  # Rating request sent
    COLLECTING_RATING = "collecting_rating"  # Waiting for 1-5 rating
    COLLECTING_FEEDBACK = "collecting_feedback"  # Optional text feedback
    SUBMITTED = "submitted"  # Rating saved

    # === Inquiry Flow ===
    INQUIRY_ANSWERED = "inquiry_answered"  # Question answered (stateless, immediate)


class CustomerFlowSession(Base, UUIDMixin, TimestampMixin):
    """Tracks a customer's conversation flow session.

    Each active customer conversation has at most one active flow session.
    When a flow completes (confirmed, cancelled, submitted), it becomes inactive.

    The flow session stores:
    - What type of flow (booking, modify, cancel, rating)
    - Current state in that flow
    - Data collected during the flow
    - Context for AI to continue the conversation
    """

    __tablename__ = "customer_flow_sessions"

    # Link to the conversation
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link to the customer
    end_customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("end_customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link to the organization (for easier querying)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Flow type and state
    flow_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CustomerFlowType.INQUIRY.value,
    )
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CustomerFlowState.INITIATED.value,
    )

    # Is this flow still active?
    is_active: Mapped[bool] = mapped_column(default=True)

    # Data collected during the flow
    collected_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Structure varies by flow type:
    #
    # Booking flow:
    # {
    #   "service_id": "uuid",
    #   "service_name": "Corte de cabello",
    #   "datetime": "2026-02-05T14:00:00",
    #   "staff_id": "uuid",  # Optional
    #   "staff_name": "María",  # Optional
    #   "customer_name": "Juan Pérez",
    #   "appointment_id": "uuid",  # After confirmation
    #   "last_active_state": "collecting_datetime"  # For abandoned state
    # }
    #
    # Modify flow:
    # {
    #   "booking_id": "uuid",
    #   "modification_type": "datetime",  # or "service", "staff"
    #   "new_datetime": "2026-02-06T15:00:00",
    #   "new_service_id": "uuid",
    #   "new_staff_id": "uuid",
    # }
    #
    # Cancel flow:
    # {
    #   "booking_id": "uuid",
    #   "booking_summary": "Corte - 5 Feb 2:00 PM",
    # }
    #
    # Rating flow:
    # {
    #   "appointment_id": "uuid",
    #   "rating": 5,
    #   "feedback": "Excelente servicio",
    # }

    # Last message timestamp (for abandoned state detection)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<CustomerFlowSession(flow_type={self.flow_type}, "
            f"state={self.state}, active={self.is_active})>"
        )

    @property
    def is_terminal_state(self) -> bool:
        """Check if the flow is in a terminal state."""
        terminal_states = {
            CustomerFlowState.CONFIRMED.value,
            CustomerFlowState.CANCELLED.value,
            CustomerFlowState.SUBMITTED.value,
            CustomerFlowState.INQUIRY_ANSWERED.value,
            CustomerFlowState.ABANDONED.value,
        }
        return self.state in terminal_states
