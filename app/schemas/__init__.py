"""Pydantic schemas for Yume API."""

from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentComplete,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.schemas.availability import (
    AvailabilityResponse,
    AvailableSlot,
    AvailableSlotRequest,
    ExceptionAvailabilityCreate,
    RecurringAvailabilityCreate,
)
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.organization import (
    OrganizationConnectWhatsApp,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.schemas.service_type import (
    ServiceTypeCreate,
    ServiceTypeResponse,
    ServiceTypeUpdate,
)
from app.schemas.spot import SpotCreate, SpotResponse, SpotUpdate
from app.schemas.staff import StaffCreate, StaffResponse, StaffUpdate

__all__ = [
    # Organization
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "OrganizationConnectWhatsApp",
    # Location
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    # Staff
    "StaffCreate",
    "StaffUpdate",
    "StaffResponse",
    # ServiceType
    "ServiceTypeCreate",
    "ServiceTypeUpdate",
    "ServiceTypeResponse",
    # Spot
    "SpotCreate",
    "SpotUpdate",
    "SpotResponse",
    # Customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    # Appointment
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    "AppointmentCancel",
    "AppointmentComplete",
    # Availability
    "RecurringAvailabilityCreate",
    "ExceptionAvailabilityCreate",
    "AvailabilityResponse",
    "AvailableSlotRequest",
    "AvailableSlot",
]
