"""ServiceType service - business logic for service types."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ServiceType
from app.schemas.service_type import ServiceTypeCreate, ServiceTypeUpdate


async def get_service_type(
    db: AsyncSession, service_type_id: UUID, organization_id: UUID
) -> ServiceType | None:
    """Get service type by ID, scoped to organization."""
    result = await db.execute(
        select(ServiceType).where(
            ServiceType.id == service_type_id,
            ServiceType.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def list_service_types(
    db: AsyncSession, organization_id: UUID, active_only: bool = True
) -> list[ServiceType]:
    """List service types for an organization."""
    query = select(ServiceType).where(ServiceType.organization_id == organization_id)
    if active_only:
        query = query.where(ServiceType.is_active == True)
    result = await db.execute(query.order_by(ServiceType.name))
    return list(result.scalars().all())


async def create_service_type(
    db: AsyncSession, organization_id: UUID, service_data: ServiceTypeCreate
) -> ServiceType:
    """Create a new service type."""
    service = ServiceType(
        organization_id=organization_id,
        name=service_data.name,
        description=service_data.description,
        duration_minutes=service_data.duration_minutes,
        price_cents=service_data.price_cents,
        currency=service_data.currency,
        is_active=service_data.is_active,
        settings=service_data.settings,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


async def update_service_type(
    db: AsyncSession, service: ServiceType, service_data: ServiceTypeUpdate
) -> ServiceType:
    """Update a service type."""
    update_dict = service_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(service, key, value)
    await db.flush()
    await db.refresh(service)
    return service


async def delete_service_type(db: AsyncSession, service: ServiceType) -> None:
    """Delete a service type (soft delete by setting is_active=False)."""
    service.is_active = False
    await db.flush()
