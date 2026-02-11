"""Pytest configuration and fixtures."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--run-evals",
        action="store_true",
        default=False,
        help="Run eval tests (requires real OPENAI_API_KEY)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip eval tests unless --run-evals is passed."""
    if config.getoption("--run-evals"):
        return
    skip_eval = pytest.mark.skip(reason="need --run-evals option to run")
    for item in items:
        if "eval" in item.keywords:
            item.add_marker(skip_eval)
from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Base,
    EndCustomer,
    Location,
    Organization,
    ServiceType,
    Spot,
    ParloUser,
)

# Aliases for compatibility
Customer = EndCustomer
Staff = ParloUser



# Use a test database
TEST_DATABASE_URL = settings.async_database_url.replace("/parlo", "/parlo_test")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def organization(db: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(
        id=uuid4(),
        name="Test Salon",
        owner_phone="+521234567890",
        timezone="America/Mexico_City",
    )
    db.add(org)
    await db.flush()
    return org


@pytest_asyncio.fixture
async def location(db: AsyncSession, organization: Organization) -> Location:
    """Create test location."""
    loc = Location(
        id=uuid4(),
        organization_id=organization.id,
        name="Main Location",
        address="123 Test St",
        is_primary=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def staff(db: AsyncSession, organization: Organization) -> Staff:
    """Create test staff member."""
    s = Staff(
        id=uuid4(),
        organization_id=organization.id,
        name="Maria",
        phone_number="+521111111111",
        is_active=True,
    )
    db.add(s)
    await db.flush()
    return s


@pytest_asyncio.fixture
async def staff2(db: AsyncSession, organization: Organization) -> Staff:
    """Create second test staff member."""
    s = Staff(
        id=uuid4(),
        organization_id=organization.id,
        name="Carlos",
        phone_number="+522222222222",
        is_active=True,
    )
    db.add(s)
    await db.flush()
    return s


@pytest_asyncio.fixture
async def customer(db: AsyncSession, organization: Organization) -> Customer:
    """Create test customer."""
    c = Customer(
        id=uuid4(),
        organization_id=organization.id,
        phone_number="+523333333333",
        name="Test Customer",
    )
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def service_type(db: AsyncSession, organization: Organization) -> ServiceType:
    """Create test service type."""
    st = ServiceType(
        id=uuid4(),
        organization_id=organization.id,
        name="Corte de cabello",
        duration_minutes=30,
        price_cents=15000,
        is_active=True,
    )
    db.add(st)
    await db.flush()
    return st


@pytest_asyncio.fixture
async def spot(db: AsyncSession, location: Location) -> Spot:
    """Create test spot."""
    s = Spot(
        id=uuid4(),
        location_id=location.id,
        name="Chair 1",
        is_active=True,
    )
    db.add(s)
    await db.flush()
    return s


@pytest_asyncio.fixture
async def spot2(db: AsyncSession, location: Location) -> Spot:
    """Create second test spot."""
    s = Spot(
        id=uuid4(),
        location_id=location.id,
        name="Chair 2",
        is_active=True,
    )
    db.add(s)
    await db.flush()
    return s
