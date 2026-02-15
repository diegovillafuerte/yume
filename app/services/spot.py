"""Spot service - business logic for spots/stations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Location, ServiceType, Spot
from app.schemas.spot import SpotCreate, SpotUpdate


async def get_spot(db: AsyncSession, spot_id: UUID, organization_id: UUID) -> Spot | None:
    """Get spot by ID, scoped to organization via location, with service types loaded."""
    result = await db.execute(
        select(Spot)
        .join(Location, Spot.location_id == Location.id)
        .where(
            Spot.id == spot_id,
            Location.organization_id == organization_id,
        )
        .options(selectinload(Spot.service_types))
    )
    return result.scalar_one_or_none()


async def list_spots(db: AsyncSession, location_id: UUID, active_only: bool = True) -> list[Spot]:
    """List all spots for a location with service types loaded."""
    query = select(Spot).where(Spot.location_id == location_id)
    if active_only:
        query = query.where(Spot.is_active == True)
    query = query.options(selectinload(Spot.service_types))
    result = await db.execute(query.order_by(Spot.display_order, Spot.name))
    return list(result.scalars().all())


async def create_spot(db: AsyncSession, location_id: UUID, spot_data: SpotCreate) -> Spot:
    """Create a new spot."""
    spot = Spot(
        location_id=location_id,
        name=spot_data.name,
        description=spot_data.description,
        is_active=spot_data.is_active,
        display_order=spot_data.display_order,
    )
    db.add(spot)
    await db.flush()
    await db.refresh(spot)
    return spot


async def update_spot(db: AsyncSession, spot: Spot, spot_data: SpotUpdate) -> Spot:
    """Update a spot."""
    update_dict = spot_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(spot, key, value)
    await db.flush()
    await db.refresh(spot)
    return spot


async def delete_spot(db: AsyncSession, spot: Spot) -> None:
    """Delete a spot (soft delete by setting is_active=False)."""
    spot.is_active = False
    await db.flush()


async def update_spot_services(
    db: AsyncSession, spot: Spot, service_type_ids: list[UUID]
) -> Spot:  # org-scope-ok: callers verify org
    """Update the services that can be performed at this spot."""
    # Fetch the service types by their IDs
    if service_type_ids:
        result = await db.execute(select(ServiceType).where(ServiceType.id.in_(service_type_ids)))
        service_types = list(result.scalars().all())
    else:
        service_types = []

    # Replace the spot's service types
    spot.service_types = service_types
    await db.flush()

    # Refresh with relationships loaded
    await db.refresh(spot, ["service_types"])
    return spot
