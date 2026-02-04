"""Staff service - business logic for staff management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Organization, ServiceType, YumeUser
from app.schemas.staff import StaffCreate, StaffUpdate


async def get_staff(db: AsyncSession, staff_id: UUID) -> YumeUser | None:
    """Get staff member by ID with service types loaded."""
    result = await db.execute(
        select(YumeUser)
        .where(YumeUser.id == staff_id)
        .options(selectinload(YumeUser.service_types))
    )
    return result.scalar_one_or_none()


async def get_all_staff_registrations(
    db: AsyncSession, phone_number: str
) -> list[tuple[YumeUser, Organization]]:
    """Get ALL active staff registrations for a phone number across all organizations.

    This is critical for the routing decision when someone messages Yume's central number.
    A person can be staff at multiple businesses (e.g., works at two salons).

    Args:
        db: Database session
        phone_number: Phone number to look up

    Returns:
        List of (YumeUser, Organization) tuples for all businesses where this phone is registered
    """
    result = await db.execute(
        select(YumeUser, Organization)
        .join(Organization, YumeUser.organization_id == Organization.id)
        .where(
            YumeUser.phone_number == phone_number,
            YumeUser.is_active == True,
        )
        .options(selectinload(YumeUser.service_types))
    )
    return list(result.all())


async def mark_first_message(db: AsyncSession, staff: YumeUser) -> YumeUser:
    """Mark that this staff member has sent their first WhatsApp message.

    Called when a pre-registered staff member messages for the first time.
    This distinguishes "needs onboarding" from "already onboarded" staff.

    Args:
        db: Database session
        staff: Staff member

    Returns:
        Updated staff member
    """
    if staff.first_message_at is None:
        staff.first_message_at = datetime.now(timezone.utc)
        await db.flush()
    return staff


def is_first_message(staff: YumeUser) -> bool:
    """Check if this would be the staff member's first WhatsApp message.

    Used to determine if we should route to staff onboarding flow.

    Args:
        staff: Staff member

    Returns:
        True if staff has never messaged before (needs onboarding)
    """
    return staff.first_message_at is None


async def get_staff_by_phone(
    db: AsyncSession, organization_id: UUID, phone_number: str
) -> YumeUser | None:
    """Get staff member by phone number within an organization.

    This is THE key function for staff identification in message routing.
    When a message arrives, we check if the sender is a registered staff member.
    """
    result = await db.execute(
        select(YumeUser).where(
            YumeUser.organization_id == organization_id,
            YumeUser.phone_number == phone_number,
            YumeUser.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def list_staff(
    db: AsyncSession, organization_id: UUID, location_id: UUID | None = None
) -> list[YumeUser]:
    """List all staff members for an organization with service types loaded."""
    query = select(YumeUser).where(YumeUser.organization_id == organization_id)
    if location_id:
        query = query.where(YumeUser.location_id == location_id)
    query = query.options(selectinload(YumeUser.service_types))
    result = await db.execute(query.order_by(YumeUser.name))
    return list(result.scalars().all())


async def create_staff(
    db: AsyncSession, organization_id: UUID, staff_data: StaffCreate
) -> YumeUser:
    """Create a new staff member."""
    staff = YumeUser(
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
    db: AsyncSession, staff: YumeUser, staff_data: StaffUpdate
) -> YumeUser:
    """Update a staff member."""
    update_dict = staff_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(staff, key, value)
    await db.flush()
    await db.refresh(staff)
    return staff


async def delete_staff(db: AsyncSession, staff: YumeUser) -> None:
    """Delete a staff member (soft delete by setting is_active=False)."""
    staff.is_active = False
    await db.flush()


async def update_staff_services(
    db: AsyncSession, staff: YumeUser, service_type_ids: list[UUID]
) -> YumeUser:
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
