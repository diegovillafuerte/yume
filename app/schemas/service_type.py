"""Pydantic schemas for ServiceType."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Base schema
class ServiceTypeBase(BaseModel):
    """Base service type schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Service name")
    description: str | None = Field(None, description="Service description")
    duration_minutes: int = Field(..., gt=0, description="Duration in minutes")
    price_cents: int = Field(..., ge=0, description="Price in cents (e.g., 15000 = $150.00 MXN)")
    currency: str = Field(default="MXN", description="Currency code")
    is_active: bool = Field(default=True, description="Is the service active")


# Schema for creating a service type
class ServiceTypeCreate(ServiceTypeBase):
    """Schema for creating a new service type."""

    settings: dict[str, Any] = Field(
        default_factory=dict, description="Service settings (e.g., requires_deposit)"
    )


# Schema for updating a service type
class ServiceTypeUpdate(BaseModel):
    """Schema for updating a service type (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int | None = Field(None, gt=0)
    price_cents: int | None = Field(None, ge=0)
    currency: str | None = None
    is_active: bool | None = None
    settings: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


# Simple schema for embedding in other responses
class ServiceTypeSummary(BaseModel):
    """Simplified service type for embedding in spot/staff responses."""

    id: UUID
    name: str
    duration_minutes: int
    price_cents: int
    currency: str = "MXN"

    model_config = ConfigDict(from_attributes=True)


# Response schema
class ServiceTypeResponse(ServiceTypeBase):
    """Schema for service type responses."""

    id: UUID
    organization_id: UUID
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
