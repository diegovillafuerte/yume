"""Spot API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_organization_dependency
from app.models import Organization, Spot
from app.schemas.spot import (
    SpotCreate,
    SpotResponse,
    SpotServiceAssignment,
    SpotUpdate,
)
from app.services import location as location_service
from app.services import spot as spot_service

router = APIRouter(tags=["spots"])


@router.get(
    "/organizations/{org_id}/locations/{location_id}/spots",
    response_model=list[SpotResponse],
    summary="List spots for a location",
)
async def list_spots(
    location_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[bool, Query(description="Only return active spots")] = True,
) -> list[Spot]:
    """List all spots for a location."""
    # Verify location belongs to organization
    location = await location_service.get_location(db, location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    spots = await spot_service.list_spots(db, location_id, active_only=active_only)
    return spots


@router.post(
    "/organizations/{org_id}/locations/{location_id}/spots",
    response_model=SpotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a spot",
)
async def create_spot(
    location_id: UUID,
    spot_data: SpotCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Spot:
    """Create a new spot for a location."""
    # Verify location belongs to organization
    location = await location_service.get_location(db, location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    spot = await spot_service.create_spot(db, location_id, spot_data)
    await db.commit()
    return spot


@router.get(
    "/organizations/{org_id}/spots/{spot_id}",
    response_model=SpotResponse,
    summary="Get spot by ID",
)
async def get_spot(
    spot_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Spot:
    """Get spot details."""
    spot = await spot_service.get_spot(db, spot_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    # Verify the spot's location belongs to the organization
    location = await location_service.get_location(db, spot.location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    return spot


@router.patch(
    "/organizations/{org_id}/spots/{spot_id}",
    response_model=SpotResponse,
    summary="Update spot",
)
async def update_spot(
    spot_id: UUID,
    spot_data: SpotUpdate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Spot:
    """Update a spot."""
    spot = await spot_service.get_spot(db, spot_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    # Verify the spot's location belongs to the organization
    location = await location_service.get_location(db, spot.location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    spot = await spot_service.update_spot(db, spot, spot_data)
    await db.commit()
    return spot


@router.delete(
    "/organizations/{org_id}/spots/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete spot",
)
async def delete_spot(
    spot_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a spot (soft delete)."""
    spot = await spot_service.get_spot(db, spot_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    # Verify the spot's location belongs to the organization
    location = await location_service.get_location(db, spot.location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    await spot_service.delete_spot(db, spot)
    await db.commit()


@router.put(
    "/organizations/{org_id}/spots/{spot_id}/services",
    response_model=SpotResponse,
    summary="Assign services to a spot",
)
async def assign_spot_services(
    spot_id: UUID,
    assignment: SpotServiceAssignment,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Spot:
    """Update which services can be performed at this spot."""
    spot = await spot_service.get_spot(db, spot_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    # Verify the spot's location belongs to the organization
    location = await location_service.get_location(db, spot.location_id)
    if not location or location.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spot {spot_id} not found",
        )

    spot = await spot_service.update_spot_services(db, spot, assignment.service_type_ids)
    await db.commit()
    return spot
