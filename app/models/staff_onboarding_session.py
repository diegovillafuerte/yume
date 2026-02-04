"""Staff onboarding session model - tracks staff onboarding via WhatsApp.

See docs/PROJECT_SPEC.md for the staff onboarding state machine:

    initiated → collecting_name → collecting_availability → showing_tutorial → completed
                      ↓                    ↓                      ↓
                  abandoned ←─────────────┴──────────────────────┘

This flow is triggered when a pre-registered staff member sends their first
message to the business's WhatsApp number (Case 3 in routing).
"""

import uuid
from enum import Enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class StaffOnboardingState(str, Enum):
    """Staff onboarding progress states.

    State machine flow:
    1. INITIATED - First message received from pre-registered staff
    2. COLLECTING_NAME - Asking for display name confirmation/update
    3. COLLECTING_AVAILABILITY - Asking for working hours preferences
    4. SHOWING_TUTORIAL - Showing capabilities and how to use Yume
    5. COMPLETED - Staff fully onboarded
    6. ABANDONED - Staff stopped responding (stores last_active_state in metadata)
    """

    INITIATED = "initiated"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_AVAILABILITY = "collecting_availability"
    SHOWING_TUTORIAL = "showing_tutorial"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StaffOnboardingSession(Base, UUIDMixin, TimestampMixin):
    """Tracks a staff member's onboarding conversation.

    This is separate from business onboarding. It's triggered when:
    1. Owner pre-registers a staff member (creates Staff record)
    2. Staff member sends first message to business WhatsApp number
    3. System detects they're staff (via phone match) but have never messaged before

    The onboarding collects:
    - Name confirmation (may update from what owner entered)
    - Availability preferences
    - Tutorial acknowledgment
    """

    __tablename__ = "staff_onboarding_sessions"

    # Link to the pre-registered staff record
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("yume_users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One onboarding session per staff
        index=True,
    )

    # Link to the organization (for easier querying)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Current state in the onboarding flow
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=StaffOnboardingState.INITIATED.value,
    )

    # Collected data during onboarding
    collected_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Structure:
    # {
    #   "name": "María López",  # Confirmed/updated name
    #   "availability": {
    #       "monday": {"start": "09:00", "end": "18:00"},
    #       "tuesday": {"start": "09:00", "end": "18:00"},
    #       ...
    #   },
    #   "tutorial_viewed": true,
    #   "last_active_state": "collecting_availability"  # For abandoned state
    # }

    # Conversation context for AI
    conversation_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:
        """String representation."""
        return f"<StaffOnboardingSession(staff_id={self.staff_id}, state={self.state})>"
