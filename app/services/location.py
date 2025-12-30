"""Location service - business logic for locations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location
from app.schemas.location import LocationCreate, LocationUpdate


async def get_location(db: AsyncSession, location_id: UUID) -> Location | None:
    """Get location by ID."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    return result.scalar_one_or_none()


async def list_locations(db: AsyncSession, organization_id: UUID) -> list[Location]:
    """List all locations for an organization."""
    query = select(Location).where(Location.organization_id == organization_id)
    result = await db.execute(query.order_by(Location.is_primary.desc(), Location.name))
    return list(result.scalars().all())


async def create_location(
    db: AsyncSession, organization_id: UUID, location_data: LocationCreate
) -> Location:
    """Create a new location."""
    location = Location(
        organization_id=organization_id,
        name=location_data.name,
        address=location_data.address,
        is_primary=location_data.is_primary,
        business_hours=location_data.business_hours,
    )
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return location


async def update_location(
    db: AsyncSession, location: Location, location_data: LocationUpdate
) -> Location:
    """Update a location."""
    update_dict = location_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(location, key, value)
    await db.flush()
    await db.refresh(location)
    return location


async def delete_location(db: AsyncSession, location: Location) -> None:
    """Delete a location.

    Note: This is a hard delete. Consider checking for related appointments first.
    """
    await db.delete(location)
    await db.flush()


async def count_locations(db: AsyncSession, organization_id: UUID) -> int:
    """Count total locations for an organization."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(Location.id)).where(Location.organization_id == organization_id)
    )
    return result.scalar_one()
