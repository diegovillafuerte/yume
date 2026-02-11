"""Seed staging environment with realistic test data.

Idempotent — safe to run multiple times. Checks for existing orgs by name.

Creates:
- "Salon Ejemplo" (active): 1 location, 3 services, 2 staff, 2 spots, availability, customers
- "Barberia Test" (active): 1 location, 2 services, 1 staff (owner), 1 spot, availability

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_staging.py
"""

import asyncio
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Availability,
    EndCustomer,
    Location,
    Organization,
    OrganizationStatus,
    ParloUser,
    ServiceType,
    Spot,
)
from app.models.associations import parlo_user_service_types, spot_service_types
from app.models.availability import AvailabilityType


async def seed_salon_ejemplo(db: AsyncSession) -> None:
    """Seed 'Salon Ejemplo' — a fully active salon with rich data."""
    # Check if already exists
    result = await db.execute(
        select(Organization).where(Organization.name == "Salon Ejemplo")
    )
    if result.scalar_one_or_none():
        print("  Salon Ejemplo already exists, skipping")
        return

    org_id = uuid4()
    loc_id = uuid4()
    staff1_id = uuid4()
    staff2_id = uuid4()
    svc1_id = uuid4()
    svc2_id = uuid4()
    svc3_id = uuid4()
    spot1_id = uuid4()
    spot2_id = uuid4()
    cust1_id = uuid4()
    cust2_id = uuid4()
    cust3_id = uuid4()

    # Organization
    org = Organization(
        id=org_id,
        name="Salon Ejemplo",
        owner_phone="+525510001001",
        timezone="America/Mexico_City",
        status=OrganizationStatus.ACTIVE.value,
        whatsapp_phone_number_id="+525510009999",
        settings={
            "twilio_phone_number": "+525510009999",
            "sender_status": "ONLINE",
            "whatsapp_ready": True,
            "number_status": "active",
        },
    )
    db.add(org)

    # Location
    loc = Location(
        id=loc_id,
        organization_id=org_id,
        name="Sucursal Centro",
        address="Av. Insurgentes Sur 1234, Col. Del Valle, CDMX",
        is_primary=True,
    )
    db.add(loc)

    # Services
    services = [
        ServiceType(
            id=svc1_id, organization_id=org_id,
            name="Corte de cabello", duration_minutes=30, price_cents=25000, is_active=True,
        ),
        ServiceType(
            id=svc2_id, organization_id=org_id,
            name="Tinte completo", duration_minutes=90, price_cents=80000, is_active=True,
        ),
        ServiceType(
            id=svc3_id, organization_id=org_id,
            name="Peinado para evento", duration_minutes=60, price_cents=50000, is_active=True,
        ),
    ]
    db.add_all(services)

    # Staff
    staff1 = ParloUser(
        id=staff1_id, organization_id=org_id,
        name="Maria Lopez", phone_number="+525510001002",
        is_active=True, is_owner=True,
        first_message_at=datetime.now(timezone.utc),
    )
    staff2 = ParloUser(
        id=staff2_id, organization_id=org_id,
        name="Carlos Ramirez", phone_number="+525510001003",
        is_active=True, is_owner=False,
        first_message_at=datetime.now(timezone.utc),
    )
    db.add_all([staff1, staff2])

    # Spots
    spot1 = Spot(id=spot1_id, location_id=loc_id, name="Silla 1", is_active=True)
    spot2 = Spot(id=spot2_id, location_id=loc_id, name="Silla 2", is_active=True)
    db.add_all([spot1, spot2])

    await db.flush()

    # Staff-service associations (Maria does all, Carlos does corte + tinte)
    await db.execute(
        insert(parlo_user_service_types).values([
            {"parlo_user_id": staff1_id, "service_type_id": svc1_id},
            {"parlo_user_id": staff1_id, "service_type_id": svc2_id},
            {"parlo_user_id": staff1_id, "service_type_id": svc3_id},
            {"parlo_user_id": staff2_id, "service_type_id": svc1_id},
            {"parlo_user_id": staff2_id, "service_type_id": svc2_id},
        ])
    )

    # Spot-service associations (both spots support all services)
    await db.execute(
        insert(spot_service_types).values([
            {"spot_id": spot1_id, "service_type_id": svc1_id},
            {"spot_id": spot1_id, "service_type_id": svc2_id},
            {"spot_id": spot1_id, "service_type_id": svc3_id},
            {"spot_id": spot2_id, "service_type_id": svc1_id},
            {"spot_id": spot2_id, "service_type_id": svc2_id},
            {"spot_id": spot2_id, "service_type_id": svc3_id},
        ])
    )

    # Availability: Mon-Sat 10:00-19:00 for both staff
    for staff_id in [staff1_id, staff2_id]:
        for day in range(0, 6):  # Mon=0 through Sat=5
            db.add(Availability(
                id=uuid4(),
                parlo_user_id=staff_id,
                type=AvailabilityType.RECURRING.value,
                day_of_week=day,
                start_time=time(10, 0),
                end_time=time(19, 0),
            ))

    # Customers
    customers = [
        EndCustomer(
            id=cust1_id, organization_id=org_id,
            phone_number="+525520001001", name="Ana Garcia",
        ),
        EndCustomer(
            id=cust2_id, organization_id=org_id,
            phone_number="+525520001002", name="Roberto Hernandez",
        ),
        EndCustomer(
            id=cust3_id, organization_id=org_id,
            phone_number="+525520001003", name="Sofia Martinez",
        ),
    ]
    db.add_all(customers)

    # A few past appointments
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    appointments = [
        Appointment(
            id=uuid4(), organization_id=org_id, location_id=loc_id,
            end_customer_id=cust1_id, parlo_user_id=staff1_id,
            spot_id=spot1_id, service_type_id=svc1_id,
            start_time=two_days_ago.replace(hour=10, minute=0),
            end_time=two_days_ago.replace(hour=10, minute=30),
            status=AppointmentStatus.COMPLETED.value,
            source=AppointmentSource.WHATSAPP.value,
        ),
        Appointment(
            id=uuid4(), organization_id=org_id, location_id=loc_id,
            end_customer_id=cust2_id, parlo_user_id=staff2_id,
            spot_id=spot2_id, service_type_id=svc2_id,
            start_time=yesterday.replace(hour=14, minute=0),
            end_time=yesterday.replace(hour=15, minute=30),
            status=AppointmentStatus.COMPLETED.value,
            source=AppointmentSource.WHATSAPP.value,
        ),
    ]
    db.add_all(appointments)

    print("  Created Salon Ejemplo with 2 staff, 3 services, 2 spots, 3 customers")


async def seed_barberia_test(db: AsyncSession) -> None:
    """Seed 'Barberia Test' — a simpler active business."""
    result = await db.execute(
        select(Organization).where(Organization.name == "Barberia Test")
    )
    if result.scalar_one_or_none():
        print("  Barberia Test already exists, skipping")
        return

    org_id = uuid4()
    loc_id = uuid4()
    staff_id = uuid4()
    svc1_id = uuid4()
    svc2_id = uuid4()
    spot_id = uuid4()

    org = Organization(
        id=org_id,
        name="Barberia Test",
        owner_phone="+525530001001",
        timezone="America/Mexico_City",
        status=OrganizationStatus.ACTIVE.value,
        whatsapp_phone_number_id="+525530009999",
        settings={
            "twilio_phone_number": "+525530009999",
            "sender_status": "ONLINE",
            "whatsapp_ready": True,
            "number_status": "active",
        },
    )
    db.add(org)

    loc = Location(
        id=loc_id, organization_id=org_id,
        name="Local Principal", address="Calle Madero 56, Centro, CDMX",
        is_primary=True,
    )
    db.add(loc)

    services = [
        ServiceType(
            id=svc1_id, organization_id=org_id,
            name="Corte clasico", duration_minutes=25, price_cents=15000, is_active=True,
        ),
        ServiceType(
            id=svc2_id, organization_id=org_id,
            name="Barba", duration_minutes=20, price_cents=10000, is_active=True,
        ),
    ]
    db.add_all(services)

    staff = ParloUser(
        id=staff_id, organization_id=org_id,
        name="Luis Morales", phone_number="+525530001002",
        is_active=True, is_owner=True,
        first_message_at=datetime.now(timezone.utc),
    )
    db.add(staff)

    spot = Spot(id=spot_id, location_id=loc_id, name="Silla 1", is_active=True)
    db.add(spot)

    await db.flush()

    await db.execute(
        insert(parlo_user_service_types).values([
            {"parlo_user_id": staff_id, "service_type_id": svc1_id},
            {"parlo_user_id": staff_id, "service_type_id": svc2_id},
        ])
    )
    await db.execute(
        insert(spot_service_types).values([
            {"spot_id": spot_id, "service_type_id": svc1_id},
            {"spot_id": spot_id, "service_type_id": svc2_id},
        ])
    )

    # Availability: Mon-Sat 9:00-18:00
    for day in range(0, 6):
        db.add(Availability(
            id=uuid4(),
            parlo_user_id=staff_id,
            type=AvailabilityType.RECURRING.value,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(18, 0),
        ))

    print("  Created Barberia Test with 1 staff, 2 services, 1 spot")


async def main() -> None:
    """Run all seed functions."""
    print("Seeding staging data...")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            await seed_salon_ejemplo(db)
            await seed_barberia_test(db)
            await db.commit()
            print("=" * 60)
            print("Done!")
        except Exception as e:
            await db.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
