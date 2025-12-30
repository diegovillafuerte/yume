"""Location API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_organization_dependency
from app.models import Location, Organization
from app.schemas.location import (
    LocationCreate,
    LocationResponse,
    LocationUpdate,
)
from app.services import location as location_service

router = APIRouter(prefix="/organizations/{org_id}/locations", tags=["locations"])


@router.get(
    "",
    response_model=list[LocationResponse],
    summary="List locations",
)
async def list_locations(
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Location]:
    """List all locations for an organization."""
    locations = await location_service.list_locations(db, org.id)
    return locations


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location",
)
async def create_location(
    location_data: LocationCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    """Create a new location."""
    location = await location_service.create_location(db, org.id, location_data)
    await db.commit()
    return location


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get location by ID",
)
async def get_location(
    location_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    """Get location details."""
    location = await location_service.get_location(db, location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )
    return location


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Update location",
)
async def update_location(
    location_id: UUID,
    location_data: LocationUpdate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    """Update a location."""
    location = await location_service.get_location(db, location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    location = await location_service.update_location(db, location, location_data)
    await db.commit()
    return location


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete location",
)
async def delete_location(
    location_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a location.

    Note: Cannot delete the last location or primary location if it's the only one.
    """
    location = await location_service.get_location(db, location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    # Check if this is the only location
    location_count = await location_service.count_locations(db, org.id)
    if location_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the only location",
        )

    await location_service.delete_location(db, location)
    await db.commit()
