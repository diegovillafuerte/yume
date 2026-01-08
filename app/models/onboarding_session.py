"""Onboarding session model - tracks business onboarding via WhatsApp."""

from enum import Enum

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class OnboardingState(str, Enum):
    """Onboarding progress states."""

    STARTED = "started"  # Just initiated
    COLLECTING_BUSINESS_INFO = "collecting_business_info"  # Getting name, type
    COLLECTING_SERVICES = "collecting_services"  # Getting services offered
    COLLECTING_HOURS = "collecting_hours"  # Getting business hours
    AWAITING_WHATSAPP_CONNECT = "awaiting_whatsapp_connect"  # Waiting for WhatsApp Business connection
    CONFIRMING = "confirming"  # Confirming all details
    COMPLETED = "completed"  # Done, org created
    ABANDONED = "abandoned"  # User stopped responding


class OnboardingSession(Base, UUIDMixin, TimestampMixin):
    """Tracks a business owner's onboarding conversation.

    This stores the progressive state as we collect business information
    through WhatsApp conversation.
    """

    __tablename__ = "onboarding_sessions"

    # Owner's phone number (the person signing up)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # Owner's name from WhatsApp profile
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Current state in the onboarding flow
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=OnboardingState.STARTED.value,
    )

    # Collected data (progressive, AI fills this in)
    collected_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Structure:
    # {
    #   "business_name": "Barbería Don Carlos",
    #   "business_type": "barbershop",  # salon, barbershop, spa, nails, etc.
    #   "owner_name": "Carlos Rodríguez",
    #   "services": [
    #       {"name": "Corte de cabello", "duration_minutes": 30, "price": 150},
    #       {"name": "Corte y barba", "duration_minutes": 45, "price": 200},
    #   ],
    #   "business_hours": {
    #       "monday": {"open": "09:00", "close": "19:00"},
    #       "tuesday": {"open": "09:00", "close": "19:00"},
    #       ...
    #   },
    #   "address": "Av. Reforma 123, Centro, CDMX"  # optional
    # }

    # Conversation context for AI
    conversation_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # The organization created after completion (null until complete)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # WhatsApp Business connection fields
    # Unique token for the connection URL (used in /connect?token=xxx)
    connection_token: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)

    # WhatsApp Business credentials (set after Meta Embedded Signup)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_waba_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Long-lived token

    def __repr__(self) -> str:
        """String representation."""
        return f"<OnboardingSession(phone={self.phone_number}, state={self.state})>"
