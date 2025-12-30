"""Staff service - business logic for staff management."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ServiceType, Staff
from app.schemas.staff import StaffCreate, StaffUpdate


async def get_staff(db: AsyncSession, staff_id: UUID) -> Staff | None:
    """Get staff member by ID with service types loaded."""
    result = await db.execute(
        select(Staff)
        .where(Staff.id == staff_id)
        .options(selectinload(Staff.service_types))
    )
    return result.scalar_one_or_none()


async def get_staff_by_phone(
    db: AsyncSession, organization_id: UUID, phone_number: str
) -> Staff | None:
    """Get staff member by phone number within an organization.

    This is THE key function for staff identification in message routing.
    When a message arrives, we check if the sender is a registered staff member.
    """
    result = await db.execute(
        select(Staff).where(
            Staff.organization_id == organization_id,
            Staff.phone_number == phone_number,
            Staff.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def list_staff(
    db: AsyncSession, organization_id: UUID, location_id: UUID | None = None
) -> list[Staff]:
    """List all staff members for an organization with service types loaded."""
    query = select(Staff).where(Staff.organization_id == organization_id)
    if location_id:
        query = query.where(Staff.location_id == location_id)
    query = query.options(selectinload(Staff.service_types))
    result = await db.execute(query.order_by(Staff.name))
    return list(result.scalars().all())


async def create_staff(
    db: AsyncSession, organization_id: UUID, staff_data: StaffCreate
) -> Staff:
    """Create a new staff member."""
    staff = Staff(
        organization_id=organization_id,
        location_id=staff_data.location_id,
        name=staff_data.name,
        phone_number=staff_data.phone_number,
        role=staff_data.role,
        permissions=staff_data.permissions,
        is_active=staff_data.is_active,
        settings=staff_data.settings,
    )
    db.add(staff)
    await db.flush()
    await db.refresh(staff)
    return staff


async def update_staff(
    db: AsyncSession, staff: Staff, staff_data: StaffUpdate
) -> Staff:
    """Update a staff member."""
    update_dict = staff_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(staff, key, value)
    await db.flush()
    await db.refresh(staff)
    return staff


async def delete_staff(db: AsyncSession, staff: Staff) -> None:
    """Delete a staff member (soft delete by setting is_active=False)."""
    staff.is_active = False
    await db.flush()


async def update_staff_services(
    db: AsyncSession, staff: Staff, service_type_ids: list[UUID]
) -> Staff:
    """Update the services that this staff member can perform."""
    # Fetch the service types by their IDs
    if service_type_ids:
        result = await db.execute(
            select(ServiceType).where(ServiceType.id.in_(service_type_ids))
        )
        service_types = list(result.scalars().all())
    else:
        service_types = []

    # Replace the staff's service types
    staff.service_types = service_types
    await db.flush()

    # Refresh with relationships loaded
    await db.refresh(staff, ["service_types"])
    return staff
