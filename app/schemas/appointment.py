"""Pydantic schemas for Appointment."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Base schema
class AppointmentBase(BaseModel):
    """Base appointment schema with common fields."""

    customer_id: UUID = Field(..., description="Customer ID")
    service_type_id: UUID = Field(..., description="Service type ID")
    staff_id: UUID | None = Field(None, description="Staff ID (null = any available)")
    scheduled_start: datetime = Field(..., description="Appointment start time (UTC)")
    scheduled_end: datetime = Field(..., description="Appointment end time (UTC)")
    notes: str | None = Field(None, description="Appointment notes")

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        """Ensure end time is after start time."""
        if "scheduled_start" in info.data and v <= info.data["scheduled_start"]:
            raise ValueError("scheduled_end must be after scheduled_start")
        return v


# Schema for creating an appointment
class AppointmentCreate(AppointmentBase):
    """Schema for creating a new appointment."""

    location_id: UUID = Field(..., description="Location ID")
    spot_id: UUID | None = Field(None, description="Spot/station ID (chair, table, etc.)")
    source: str = Field(
        default="whatsapp", description="Source: whatsapp, web, manual, walk_in"
    )


# Schema for updating an appointment
class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment (all fields optional)."""

    staff_id: UUID | None = None
    spot_id: UUID | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    status: str | None = Field(
        None, description="Status: pending, confirmed, completed, cancelled, no_show"
    )
    notes: str | None = None
    cancellation_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


# Schema for cancelling an appointment
class AppointmentCancel(BaseModel):
    """Schema for cancelling an appointment."""

    cancellation_reason: str | None = Field(None, description="Reason for cancellation")


# Schema for completing an appointment
class AppointmentComplete(BaseModel):
    """Schema for marking appointment as completed."""

    notes: str | None = Field(None, description="Notes about the completed appointment")


# Response schema
class AppointmentResponse(AppointmentBase):
    """Schema for appointment responses."""

    id: UUID
    organization_id: UUID
    location_id: UUID
    spot_id: UUID | None
    status: str
    source: str
    cancellation_reason: str | None
    reminder_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
