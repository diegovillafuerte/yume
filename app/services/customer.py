"""Customer service - business logic for customer management."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EndCustomer
from app.schemas.customer import CustomerCreate, CustomerUpdate


async def get_customer(db: AsyncSession, customer_id: UUID) -> EndCustomer | None:
    """Get customer by ID."""
    result = await db.execute(select(EndCustomer).where(EndCustomer.id == customer_id))
    return result.scalar_one_or_none()


async def get_customer_by_phone(
    db: AsyncSession, organization_id: UUID, phone_number: str
) -> EndCustomer | None:
    """Get customer by phone number within an organization."""
    result = await db.execute(
        select(EndCustomer).where(
            EndCustomer.organization_id == organization_id,
            EndCustomer.phone_number == phone_number,
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_customer(
    db: AsyncSession, organization_id: UUID, phone_number: str, name: str | None = None
) -> EndCustomer:
    """Get or create customer by phone number (incremental identity pattern).

    This is THE key function for customer identity in message routing.
    Customers can exist with just a phone number initially.
    Name and other details are added over time during conversations.
    """
    customer = await get_customer_by_phone(db, organization_id, phone_number)
    if customer:
        return customer

    # Create new customer with just phone number
    customer = EndCustomer(
        organization_id=organization_id,
        phone_number=phone_number,
        name=name,  # May be None initially
        settings={},
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


async def list_customers(
    db: AsyncSession, organization_id: UUID, skip: int = 0, limit: int = 100
) -> list[EndCustomer]:
    """List customers for an organization with pagination."""
    result = await db.execute(
        select(EndCustomer)
        .where(EndCustomer.organization_id == organization_id)
        .order_by(EndCustomer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_customer(
    db: AsyncSession, organization_id: UUID, customer_data: CustomerCreate
) -> EndCustomer:
    """Create a new customer."""
    customer = EndCustomer(
        organization_id=organization_id,
        phone_number=customer_data.phone_number,
        name=customer_data.name,
        email=customer_data.email,
        notes=customer_data.notes,
        settings=customer_data.settings,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


async def update_customer(
    db: AsyncSession, customer: EndCustomer, customer_data: CustomerUpdate
) -> EndCustomer:
    """Update a customer."""
    update_dict = customer_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(customer, key, value)
    await db.flush()
    await db.refresh(customer)
    return customer
