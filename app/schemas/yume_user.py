"""YumeUser schemas for API requests and responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.service_type import ServiceTypeSummary


class YumeUserBase(BaseModel):
    """Base yume user schema with common fields."""

    name: str = Field(..., min_length=1)
    phone_number: str = Field(..., description="WhatsApp number for identification")
    role: Literal["owner", "employee"] = Field(default="employee")
    permissions: dict = Field(
        default_factory=dict, description="Permission flags like {can_view_schedule: true}"
    )
    is_active: bool = Field(default=True)
    settings: dict = Field(default_factory=dict)


class YumeUserCreate(BaseModel):
    """Schema for creating a new yume user."""

    name: str = Field(..., min_length=1)
    phone_number: str = Field(..., description="WhatsApp number")
    role: Literal["owner", "employee"] = Field(default="employee")
    location_id: UUID | None = Field(None)
    default_spot_id: UUID | None = Field(None)
    permissions: dict = Field(default_factory=dict)
    is_active: bool = Field(default=True)
    settings: dict = Field(default_factory=dict)


class YumeUserUpdate(BaseModel):
    """Schema for updating a yume user - all fields optional."""

    name: str | None = Field(None)
    phone_number: str | None = Field(None)
    role: Literal["owner", "employee"] | None = Field(None)
    location_id: UUID | None = Field(None)
    default_spot_id: UUID | None = Field(None)
    permissions: dict | None = Field(None)
    is_active: bool | None = Field(None)
    settings: dict | None = Field(None)


class YumeUserResponse(YumeUserBase):
    """Schema for yume user API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    location_id: UUID | None
    default_spot_id: UUID | None
    service_types: list[ServiceTypeSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class YumeUserServiceAssignment(BaseModel):
    """Schema for assigning services to a yume user."""

    service_type_ids: list[UUID] = Field(
        ..., description="List of service type IDs this yume user can perform"
    )
