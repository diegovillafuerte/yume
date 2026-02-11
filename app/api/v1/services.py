"""ServiceType API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_org_access
from app.models import Organization, ServiceType
from app.schemas.service_type import (
    ServiceTypeCreate,
    ServiceTypeResponse,
    ServiceTypeUpdate,
)
from app.services import service_type as service_service

router = APIRouter(prefix="/organizations/{org_id}/services", tags=["services"])


@router.get(
    "",
    response_model=list[ServiceTypeResponse],
    summary="List service types",
)
async def list_services(
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[bool, Query(description="Only return active services")] = True,
) -> list[ServiceType]:
    """List all service types for an organization."""
    services = await service_service.list_service_types(db, org.id, active_only=active_only)
    return services


@router.post(
    "",
    response_model=ServiceTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a service type",
)
async def create_service(
    service_data: ServiceTypeCreate,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceType:
    """Create a new service type."""
    service = await service_service.create_service_type(db, org.id, service_data)
    await db.commit()
    return service


@router.get(
    "/{service_id}",
    response_model=ServiceTypeResponse,
    summary="Get service type by ID",
)
async def get_service(
    service_id: UUID,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceType:
    """Get service type details."""
    service = await service_service.get_service_type(db, service_id)
    if not service or service.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service type {service_id} not found",
        )
    return service


@router.patch(
    "/{service_id}",
    response_model=ServiceTypeResponse,
    summary="Update service type",
)
async def update_service(
    service_id: UUID,
    service_data: ServiceTypeUpdate,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceType:
    """Update a service type."""
    service = await service_service.get_service_type(db, service_id)
    if not service or service.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service type {service_id} not found",
        )

    service = await service_service.update_service_type(db, service, service_data)
    await db.commit()
    return service


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete service type",
)
async def delete_service(
    service_id: UUID,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a service type (soft delete)."""
    service = await service_service.get_service_type(db, service_id)
    if not service or service.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service type {service_id} not found",
        )

    await service_service.delete_service_type(db, service)
    await db.commit()
