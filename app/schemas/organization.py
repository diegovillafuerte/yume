"""Pydantic schemas for Organization."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Base schema with common fields
class OrganizationBase(BaseModel):
    """Base organization schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Business name")
    phone_country_code: str = Field(..., description="Country code (e.g., +52 for Mexico)")
    phone_number: str = Field(..., description="WhatsApp-connected phone number")
    timezone: str = Field(
        default="America/Mexico_City", description="Organization timezone"
    )


# Schema for creating a new organization
class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""

    settings: dict[str, Any] = Field(default_factory=dict, description="Organization settings")


# Schema for updating an organization
class OrganizationUpdate(BaseModel):
    """Schema for updating an organization (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    timezone: str | None = None
    settings: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


# Schema for WhatsApp connection
class OrganizationConnectWhatsApp(BaseModel):
    """Schema for connecting WhatsApp via Embedded Signup."""

    whatsapp_phone_number_id: str = Field(..., description="Meta's phone number ID")
    whatsapp_waba_id: str = Field(..., description="WhatsApp Business Account ID")
    phone_number: str = Field(..., description="Business WhatsApp phone number (E.164)")


# Response schema
class OrganizationResponse(OrganizationBase):
    """Schema for organization responses."""

    id: UUID
    whatsapp_phone_number_id: str | None = None
    whatsapp_waba_id: str | None = None
    status: str
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
