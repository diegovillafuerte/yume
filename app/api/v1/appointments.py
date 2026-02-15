"""Appointment API endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_org_access
from app.models import Appointment, EndCustomer, Organization, ParloUser, ServiceType
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentComplete,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.services import scheduling as scheduling_service

router = APIRouter(prefix="/organizations/{org_id}/appointments", tags=["appointments"])


@router.get(
    "",
    response_model=list[AppointmentResponse],
    summary="List appointments",
)
async def list_appointments(
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: Annotated[date | None, Query(description="Filter by start date")] = None,
    end_date: Annotated[date | None, Query(description="Filter by end date")] = None,
    customer_id: Annotated[UUID | None, Query(description="Filter by customer ID")] = None,
    staff_id: Annotated[UUID | None, Query(description="Filter by staff ID")] = None,
) -> list[Appointment]:
    """List appointments with optional filters."""
    appointments = await scheduling_service.list_appointments(
        db,
        org.id,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        staff_id=staff_id,
    )
    return appointments


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an appointment",
)
async def create_appointment(
    appointment_data: AppointmentCreate,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Appointment:
    """Create a new appointment."""
    # Check for conflicts before creating
    conflicts = await scheduling_service.check_appointment_conflicts(
        db=db,
        organization_id=org.id,
        staff_id=appointment_data.parlo_user_id,
        spot_id=appointment_data.spot_id,
        start_time=appointment_data.scheduled_start,
        end_time=appointment_data.scheduled_end,
    )

    if conflicts:
        # Build descriptive error message
        conflict = conflicts[0]
        conflict_start = conflict.scheduled_start.strftime("%I:%M %p")
        conflict_end = conflict.scheduled_end.strftime("%I:%M %p")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cita en ese horario ({conflict_start} - {conflict_end}). Por favor selecciona otro horario.",
        )

    # Validate customer exists and belongs to org
    if appointment_data.end_customer_id:
        customer = await db.get(EndCustomer, appointment_data.end_customer_id)
        if not customer or customer.organization_id != org.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {appointment_data.end_customer_id} not found",
            )

    # Validate staff exists and belongs to org
    if appointment_data.parlo_user_id:
        staff = await db.get(ParloUser, appointment_data.parlo_user_id)
        if not staff or staff.organization_id != org.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff member {appointment_data.parlo_user_id} not found",
            )

    # Validate service type exists and belongs to org
    service = await db.get(ServiceType, appointment_data.service_type_id)
    if not service or service.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service type {appointment_data.service_type_id} not found",
        )

    try:
        appointment = await scheduling_service.create_appointment(db, org.id, appointment_data)
        await db.commit()
        return appointment
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cita en ese horario. Por favor selecciona otro horario.",
        ) from None


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment by ID",
)
async def get_appointment(
    appointment_id: UUID,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Appointment:
    """Get appointment details."""
    appointment = await scheduling_service.get_appointment(db, appointment_id, org.id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {appointment_id} not found",
        )
    return appointment


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Update appointment",
)
async def update_appointment(
    appointment_id: UUID,
    appointment_data: AppointmentUpdate,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Appointment:
    """Update an appointment."""
    appointment = await scheduling_service.get_appointment(db, appointment_id, org.id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {appointment_id} not found",
        )

    try:
        appointment = await scheduling_service.update_appointment(db, appointment, appointment_data)
        await db.commit()
        return appointment
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cita en ese horario. Por favor selecciona otro horario.",
        ) from None


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel appointment",
)
async def cancel_appointment(
    appointment_id: UUID,
    cancel_data: AppointmentCancel,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Appointment:
    """Cancel an appointment."""
    appointment = await scheduling_service.get_appointment(db, appointment_id, org.id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {appointment_id} not found",
        )

    appointment = await scheduling_service.cancel_appointment(
        db, appointment, reason=cancel_data.cancellation_reason
    )
    await db.commit()
    return appointment


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    summary="Mark appointment as completed",
)
async def complete_appointment(
    appointment_id: UUID,
    complete_data: AppointmentComplete,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Appointment:
    """Mark an appointment as completed."""
    appointment = await scheduling_service.get_appointment(db, appointment_id, org.id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {appointment_id} not found",
        )

    appointment = await scheduling_service.complete_appointment(
        db, appointment, notes=complete_data.notes
    )
    await db.commit()
    return appointment
