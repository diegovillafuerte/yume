"""EndCustomer schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EndCustomerBase(BaseModel):
    """Base end customer schema with common fields."""

    phone_number: str = Field(..., description="Primary identifier - phone number")
    name: str | None = Field(None, description="Name (learned over time)")
    email: str | None = Field(None)
    notes: str | None = Field(None, description="Business owner's notes about this end customer")
    settings: dict = Field(default_factory=dict)


class EndCustomerCreate(BaseModel):
    """Schema for creating a new end customer.

    Only phone_number is required initially (incremental identity).
    """

    phone_number: str = Field(..., description="WhatsApp phone number")
    name: str | None = Field(None)


class EndCustomerUpdate(BaseModel):
    """Schema for updating an end customer - all fields optional."""

    phone_number: str | None = Field(None)
    name: str | None = Field(None)
    email: str | None = Field(None)
    notes: str | None = Field(None)
    settings: dict | None = Field(None)


class EndCustomerResponse(EndCustomerBase):
    """Schema for end customer API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
