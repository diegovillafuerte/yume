"""Availability API endpoints - scheduling and slot calculation."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_organization_dependency
from app.models import Availability, AvailabilityType, Location, Organization, YumeUser
from app.schemas.availability import (
    AvailabilityResponse,
    AvailableSlot,
    AvailableSlotRequest,
    ExceptionAvailabilityCreate,
    RecurringAvailabilityCreate,
)
from app.services import scheduling as scheduling_service

router = APIRouter(prefix="/organizations/{org_id}/availability", tags=["availability"])


@router.post(
    "/recurring",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create recurring availability",
)
async def create_recurring_availability(
    availability_data: RecurringAvailabilityCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Availability:
    """Create recurring availability for a staff member (e.g., Mon-Fri 9-5)."""
    # Validate staff belongs to org
    staff = await db.get(YumeUser, availability_data.staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {availability_data.staff_id} not found",
        )

    availability = Availability(
        staff_id=availability_data.staff_id,
        type=AvailabilityType.RECURRING.value,
        day_of_week=availability_data.day_of_week,
        start_time=availability_data.start_time,
        end_time=availability_data.end_time,
    )
    db.add(availability)
    await db.flush()
    await db.refresh(availability)
    await db.commit()
    return availability


@router.post(
    "/exceptions",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exception availability",
)
async def create_exception_availability(
    availability_data: ExceptionAvailabilityCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Availability:
    """Create exception availability (time off, special hours for specific date)."""
    # Validate staff belongs to org
    staff = await db.get(YumeUser, availability_data.staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {availability_data.staff_id} not found",
        )

    availability = Availability(
        staff_id=availability_data.staff_id,
        type=AvailabilityType.EXCEPTION.value,
        exception_date=availability_data.exception_date,
        is_available=availability_data.is_available,
        start_time=availability_data.start_time,
        end_time=availability_data.end_time,
    )
    db.add(availability)
    await db.flush()
    await db.refresh(availability)
    await db.commit()
    return availability


@router.get(
    "/staff/{staff_id}",
    response_model=list[AvailabilityResponse],
    summary="Get staff availability",
)
async def get_staff_availability(
    staff_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Availability]:
    """Get all availability records for a staff member."""
    # Validate staff belongs to org
    staff = await db.get(YumeUser, staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {staff_id} not found",
        )

    result = await db.execute(
        select(Availability)
        .where(Availability.staff_id == staff_id)
        .order_by(Availability.type, Availability.day_of_week, Availability.exception_date)
    )
    return list(result.scalars().all())


@router.delete(
    "/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete availability",
)
async def delete_availability(
    availability_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an availability record."""
    result = await db.execute(
        select(Availability).where(Availability.id == availability_id)
    )
    availability = result.scalar_one_or_none()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Availability {availability_id} not found",
        )

    # Validate staff belongs to org
    staff = await db.get(YumeUser, availability.staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Availability {availability_id} not found",
        )

    await db.delete(availability)
    await db.commit()


@router.post(
    "/slots",
    response_model=list[AvailableSlot],
    summary="Get available appointment slots",
)
async def get_available_slots(
    request: AvailableSlotRequest,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AvailableSlot]:
    """Calculate available appointment slots (THE core scheduling algorithm).

    This endpoint:
    1. Takes a service type and date range
    2. Finds all staff who can perform this service
    3. Calculates their available time slots based on:
       - Recurring availability (weekly schedule)
       - Exceptions (time off, special hours)
       - Existing appointments (removes conflicts)
    4. Returns list of available slots with staff assignments

    This is used by:
    - AI to offer slot options to customers
    - Dashboard to view availability
    - Customers to see what times are open
    """
    # Get first location for this org (MVP: use first location)
    location_result = await db.execute(
        select(Location).where(Location.organization_id == org.id).limit(1)
    )
    location = location_result.scalar_one_or_none()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization has no locations configured",
        )

    date_to = request.date_to if request.date_to else request.date_from

    slots = await scheduling_service.get_available_slots(
        db=db,
        organization_id=org.id,
        location_id=location.id,
        service_type_id=request.service_type_id,
        date_from=request.date_from,
        date_to=date_to,
        staff_id=request.staff_id,
    )

    return slots
