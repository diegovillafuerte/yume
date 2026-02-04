"""Staff API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_organization_dependency
from app.models import Organization, YumeUser
from app.schemas.staff import StaffCreate, StaffResponse, StaffServiceAssignment, StaffUpdate
from app.services import staff as staff_service

router = APIRouter(prefix="/organizations/{org_id}/staff", tags=["staff"])


@router.get(
    "",
    response_model=list[StaffResponse],
    summary="List staff members",
)
async def list_staff(
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: Annotated[
        UUID | None, Query(description="Filter by location ID")
    ] = None,
) -> list[YumeUser]:
    """List all staff members for an organization."""
    staff_list = await staff_service.list_staff(db, org.id, location_id=location_id)
    return staff_list


@router.post(
    "",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff member",
)
async def create_staff(
    staff_data: StaffCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> YumeUser:
    """Create a new staff member.

    The phone number will be used to identify this person as staff
    when they message the business WhatsApp number.
    """
    # Check if phone number is already registered
    existing = await staff_service.get_staff_by_phone(db, org.id, staff_data.phone_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Staff member with phone number {staff_data.phone_number} already exists",
        )

    staff = await staff_service.create_staff(db, org.id, staff_data)
    await db.commit()
    return staff


@router.get(
    "/lookup",
    response_model=StaffResponse | None,
    summary="Lookup staff by phone number",
)
async def lookup_staff_by_phone(
    phone_number: Annotated[str, Query(description="Phone number to lookup")],
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> YumeUser | None:
    """Lookup staff member by phone number (for message routing).

    This endpoint is used to determine if an incoming WhatsApp message
    is from a staff member or a customer.
    """
    staff = await staff_service.get_staff_by_phone(db, org.id, phone_number)
    return staff


@router.get(
    "/{staff_id}",
    response_model=StaffResponse,
    summary="Get staff member by ID",
)
async def get_staff(
    staff_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> YumeUser:
    """Get staff member details."""
    staff = await staff_service.get_staff(db, staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {staff_id} not found",
        )
    return staff


@router.patch(
    "/{staff_id}",
    response_model=StaffResponse,
    summary="Update staff member",
)
async def update_staff(
    staff_id: UUID,
    staff_data: StaffUpdate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> YumeUser:
    """Update a staff member."""
    staff = await staff_service.get_staff(db, staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {staff_id} not found",
        )

    # If updating phone number, check for conflicts
    if staff_data.phone_number and staff_data.phone_number != staff.phone_number:
        existing = await staff_service.get_staff_by_phone(
            db, org.id, staff_data.phone_number
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone number {staff_data.phone_number} already registered",
            )

    staff = await staff_service.update_staff(db, staff, staff_data)
    await db.commit()
    return staff


@router.delete(
    "/{staff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete staff member",
)
async def delete_staff(
    staff_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a staff member (soft delete)."""
    staff = await staff_service.get_staff(db, staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {staff_id} not found",
        )

    await staff_service.delete_staff(db, staff)
    await db.commit()


@router.put(
    "/{staff_id}/services",
    response_model=StaffResponse,
    summary="Assign services to a staff member",
)
async def assign_staff_services(
    staff_id: UUID,
    assignment: StaffServiceAssignment,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> YumeUser:
    """Update which services this staff member can perform."""
    staff = await staff_service.get_staff(db, staff_id)
    if not staff or staff.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member {staff_id} not found",
        )

    staff = await staff_service.update_staff_services(db, staff, assignment.service_type_ids)
    await db.commit()
    return staff
