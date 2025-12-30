"""Admin-specific Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Auth schemas
class AdminLoginRequest(BaseModel):
    """Admin login request."""

    password: str = Field(..., description="Admin master password")


class AdminLoginResponse(BaseModel):
    """Admin login response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Organization schemas for admin
class AdminOrganizationSummary(BaseModel):
    """Organization summary for admin list view."""

    id: UUID
    name: str
    phone_number: str
    phone_country_code: str
    status: str
    whatsapp_connected: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminOrganizationDetail(AdminOrganizationSummary):
    """Detailed organization view for admin."""

    timezone: str
    settings: dict
    location_count: int
    staff_count: int
    customer_count: int
    appointment_count: int


# Stats schemas
class AdminStats(BaseModel):
    """Platform-wide statistics."""

    organizations: dict  # {total, active, onboarding, suspended, churned}
    appointments: dict  # {total, pending, confirmed, completed, cancelled, no_show}
    customers_total: int
    messages_total: int


# Conversation schemas
class AdminConversationSummary(BaseModel):
    """Conversation summary for admin list view."""

    id: UUID
    organization_id: UUID
    organization_name: str
    customer_phone: str
    customer_name: str | None
    status: str
    message_count: int
    last_message_at: datetime | None
    created_at: datetime


class AdminMessageDetail(BaseModel):
    """Message detail for conversation viewer."""

    id: UUID
    direction: str
    sender_type: str
    content: str
    content_type: str
    created_at: datetime


class AdminConversationDetail(AdminConversationSummary):
    """Detailed conversation with messages."""

    messages: list[AdminMessageDetail]


# Activity feed schemas
class AdminActivityItem(BaseModel):
    """Activity feed item."""

    id: UUID
    timestamp: datetime
    organization_id: UUID
    organization_name: str
    action_type: str  # org_created, appointment_booked, appointment_completed, etc.
    details: dict


# Impersonation schema
class AdminImpersonateResponse(BaseModel):
    """Response when impersonating an organization."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    organization: AdminOrganizationSummary


# Suspend/Reactivate
class AdminOrgStatusUpdate(BaseModel):
    """Request to update organization status."""

    status: str = Field(..., description="New status: 'active' or 'suspended'")
