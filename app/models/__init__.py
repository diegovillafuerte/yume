"""SQLAlchemy models for Yume."""

from app.models.appointment import Appointment, AppointmentSource, AppointmentStatus
from app.models.associations import spot_service_types, yume_user_service_types
from app.models.auth_token import AuthToken, TokenType
from app.models.availability import Availability, AvailabilityType
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.conversation import Conversation, ConversationStatus
from app.models.end_customer import EndCustomer
from app.models.execution_trace import ExecutionTrace, ExecutionTraceType
from app.models.function_trace import FunctionTrace, FunctionTraceType
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
from app.models.yume_user import YumeUser, YumeUserPermissionLevel, YumeUserRole
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.staff_onboarding_session import StaffOnboardingSession, StaffOnboardingState
from app.models.customer_flow_session import CustomerFlowSession, CustomerFlowState, CustomerFlowType

# Aliases for backward compatibility
Staff = YumeUser
StaffRole = YumeUserRole
Customer = EndCustomer

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
    "Staff",  # Alias for YumeUser
    "ServiceType",
    "EndCustomer",
    "Customer",  # Alias for EndCustomer
    "Appointment",
    "Conversation",
    "Message",
    "Availability",
    "AuthToken",
    "ExecutionTrace",
    "FunctionTrace",
    # Association Tables
    "spot_service_types",
    "yume_user_service_types",
    # Enums
    "OrganizationStatus",
    "YumeUserRole",
    "StaffRole",  # Alias for YumeUserRole
    "YumeUserPermissionLevel",
    "AppointmentStatus",
    "AppointmentSource",
    "ConversationStatus",
    "MessageDirection",
    "MessageSenderType",
    "MessageContentType",
    "AvailabilityType",
    "TokenType",
    "ExecutionTraceType",
    "FunctionTraceType",
    "OnboardingSession",
    "OnboardingState",
    "StaffOnboardingSession",
    "StaffOnboardingState",
    "CustomerFlowSession",
    "CustomerFlowState",
    "CustomerFlowType",
]
