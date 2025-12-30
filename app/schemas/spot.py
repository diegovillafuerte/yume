"""Pydantic schemas for Spot."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.service_type import ServiceTypeSummary


# Base schema
class SpotBase(BaseModel):
    """Base spot schema with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Spot name (e.g., 'Silla 1', 'Mesa 2')")
    description: str | None = Field(None, description="Spot description")
    is_active: bool = Field(default=True, description="Is the spot active")
    display_order: int = Field(default=0, description="Order for display in UI")


# Schema for creating a spot
class SpotCreate(SpotBase):
    """Schema for creating a new spot."""

    pass


# Schema for updating a spot
class SpotUpdate(BaseModel):
    """Schema for updating a spot (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None

    model_config = ConfigDict(extra="forbid")


# Schema for assigning services to a spot
class SpotServiceAssignment(BaseModel):
    """Schema for assigning services to a spot."""

    service_type_ids: list[UUID] = Field(..., description="List of service type IDs to assign")


# Response schema
class SpotResponse(SpotBase):
    """Schema for spot responses."""

    id: UUID
    location_id: UUID
    created_at: datetime
    updated_at: datetime
    service_types: list[ServiceTypeSummary] = Field(default_factory=list, description="Services that can be performed at this spot")

    model_config = ConfigDict(from_attributes=True)
