"""SQLAlchemy models for Yume."""

from app.models.appointment import Appointment, AppointmentSource, AppointmentStatus
from app.models.associations import spot_service_types, yume_user_service_types
from app.models.auth_token import AuthToken, TokenType
from app.models.availability import Availability, AvailabilityType
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.conversation import Conversation, ConversationStatus
from app.models.end_customer import EndCustomer
from app.models.execution_trace import ExecutionTrace, ExecutionTraceType
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
from app.models.yume_user import YumeUser, YumeUserRole
from app.models.onboarding_session import OnboardingSession, OnboardingState

# Backwards compatibility aliases (deprecated, use new names)
Customer = EndCustomer
Staff = YumeUser
StaffRole = YumeUserRole
staff_service_types = yume_user_service_types

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    # Models
    "Organization",
    "Location",
    "Spot",
    "YumeUser",
    "ServiceType",
    "EndCustomer",
    "Appointment",
    "Conversation",
    "Message",
    "Availability",
    "AuthToken",
    "ExecutionTrace",
    # Association Tables
    "spot_service_types",
    "yume_user_service_types",
    # Enums
    "OrganizationStatus",
    "YumeUserRole",
    "AppointmentStatus",
    "AppointmentSource",
    "ConversationStatus",
    "MessageDirection",
    "MessageSenderType",
    "MessageContentType",
    "AvailabilityType",
    "TokenType",
    "ExecutionTraceType",
    "OnboardingSession",
    "OnboardingState",
    # Backwards compatibility aliases (deprecated)
    "Customer",  # Use EndCustomer
    "Staff",  # Use YumeUser
    "StaffRole",  # Use YumeUserRole
    "staff_service_types",  # Use yume_user_service_types
]
