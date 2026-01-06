"""SQLAlchemy models for Yume."""

from app.models.appointment import Appointment, AppointmentSource, AppointmentStatus
from app.models.associations import spot_service_types, staff_service_types
from app.models.auth_token import AuthToken, TokenType
from app.models.availability import Availability, AvailabilityType
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.conversation import Conversation, ConversationStatus
from app.models.customer import Customer
from app.models.location import Location
from app.models.message import (
    Message,
    MessageContentType,
    MessageDirection,
    MessageSenderType,
)
from app.models.organization import Organization, OrganizationStatus
from app.models.service_type import ServiceType
from app.models.spot import Spot
from app.models.staff import Staff, StaffRole
from app.models.onboarding_session import OnboardingSession, OnboardingState

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    # Models
    "Organization",
    "Location",
    "Spot",
    "Staff",
    "ServiceType",
    "Customer",
    "Appointment",
    "Conversation",
    "Message",
    "Availability",
    "AuthToken",
    # Association Tables
    "spot_service_types",
    "staff_service_types",
    # Enums
    "OrganizationStatus",
    "StaffRole",
    "AppointmentStatus",
    "AppointmentSource",
    "ConversationStatus",
    "MessageDirection",
    "MessageSenderType",
    "MessageContentType",
    "AvailabilityType",
    "TokenType",
    "OnboardingSession",
    "OnboardingState",
]
