"""Customer API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_db, get_organization_dependency
from app.models import EndCustomer, Organization
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services import customer as customer_service

router = APIRouter(prefix="/organizations/{org_id}/customers", tags=["customers"])


@router.get(
    "",
    response_model=list[CustomerResponse],
    summary="List customers",
)
async def list_customers(
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[EndCustomer]:
    """List customers for an organization with pagination."""
    customers = await customer_service.list_customers(
        db, org.id, skip=pagination.skip, limit=pagination.limit
    )
    return customers


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer",
)
async def create_customer(
    customer_data: CustomerCreate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndCustomer:
    """Create a new customer (incremental identity - only phone required)."""
    # Check if customer already exists with this phone
    existing = await customer_service.get_customer_by_phone(
        db, org.id, customer_data.phone_number
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with phone number {customer_data.phone_number} already exists",
        )

    customer = await customer_service.create_customer(db, org.id, customer_data)
    await db.commit()
    return customer


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
)
async def get_customer(
    customer_id: UUID,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndCustomer:
    """Get customer details."""
    customer = await customer_service.get_customer(db, customer_id)
    if not customer or customer.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    return customer


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerUpdate,
    org: Annotated[Organization, Depends(get_organization_dependency)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndCustomer:
    """Update a customer (incremental identity - enrich data over time)."""
    customer = await customer_service.get_customer(db, customer_id)
    if not customer or customer.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )

    # If updating phone number, check for conflicts
    if customer_data.phone_number and customer_data.phone_number != customer.phone_number:
        existing = await customer_service.get_customer_by_phone(
            db, org.id, customer_data.phone_number
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone number {customer_data.phone_number} already registered",
            )

    customer = await customer_service.update_customer(db, customer, customer_data)
    await db.commit()
    return customer
