"""Shared seed functions for eval tests.

Each helper creates a self-contained set of test data and returns
the created objects as a dict for easy access in tests.
"""

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

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


async def seed_active_business(db: AsyncSession) -> dict:
    """Create an active business with full configuration.

    Creates:
    - Organization (active, with WhatsApp number)
    - Location
    - 1 staff (owner)
    - 1 service ("Corte de cabello", 30min, $250)
    - 1 spot
    - Availability: Mon-Sat 10:00-19:00 (America/Mexico_City)
    - Staff-service + spot-service associations

    Returns dict with all created objects.
    """
    org_id = uuid4()
    loc_id = uuid4()
    staff_id = uuid4()
    svc_id = uuid4()
    spot_id = uuid4()

    org = Organization(
        id=org_id,
        name="Eval Test Salon",
        owner_phone="+525599001001",
        timezone="America/Mexico_City",
        status=OrganizationStatus.ACTIVE.value,
        whatsapp_phone_number_id="+525599009999",
        settings={
            "twilio_phone_number": "+525599009999",
            "sender_status": "ONLINE",
            "whatsapp_ready": True,
        },
    )
    db.add(org)

    loc = Location(
        id=loc_id,
        organization_id=org_id,
        name="Sucursal Principal",
        address="Test Address 123",
        is_primary=True,
    )
    db.add(loc)

    svc = ServiceType(
        id=svc_id,
        organization_id=org_id,
        name="Corte de cabello",
        duration_minutes=30,
        price_cents=25000,
        is_active=True,
    )
    db.add(svc)

    staff = ParloUser(
        id=staff_id,
        organization_id=org_id,
        name="Maria Eval",
        phone_number="+525599001002",
        is_active=True,
        is_owner=True,
        first_message_at=datetime.now(timezone.utc),
    )
    db.add(staff)

    spot = Spot(
        id=spot_id,
        location_id=loc_id,
        name="Silla 1",
        is_active=True,
    )
    db.add(spot)

    await db.flush()

    # Associations
    await db.execute(
        insert(parlo_user_service_types).values([
            {"parlo_user_id": staff_id, "service_type_id": svc_id},
        ])
    )
    await db.execute(
        insert(spot_service_types).values([
            {"spot_id": spot_id, "service_type_id": svc_id},
        ])
    )

    # Availability: Mon-Sat 10:00-19:00
    for day in range(0, 6):
        db.add(Availability(
            id=uuid4(),
            parlo_user_id=staff_id,
            type=AvailabilityType.RECURRING.value,
            day_of_week=day,
            start_time=time(10, 0),
            end_time=time(19, 0),
        ))

    await db.flush()

    return {
        "org": org,
        "location": loc,
        "staff": staff,
        "service": svc,
        "spot": spot,
    }


async def seed_business_with_appointments(db: AsyncSession) -> dict:
    """Create an active business with existing appointments and customers.

    Extends seed_active_business with:
    - 2 customers
    - 1 completed appointment (yesterday)
    - 1 confirmed appointment (tomorrow at 10:00)

    Returns dict with all objects.
    """
    data = await seed_active_business(db)
    org = data["org"]
    loc = data["location"]
    staff = data["staff"]
    svc = data["service"]
    spot = data["spot"]

    cust1_id = uuid4()
    cust2_id = uuid4()

    cust1 = EndCustomer(
        id=cust1_id,
        organization_id=org.id,
        phone_number="+525588001001",
        name="Ana Garcia",
    )
    cust2 = EndCustomer(
        id=cust2_id,
        organization_id=org.id,
        phone_number="+525588001002",
        name="Roberto Hernandez",
    )
    db.add_all([cust1, cust2])

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    past_apt = Appointment(
        id=uuid4(),
        organization_id=org.id,
        location_id=loc.id,
        end_customer_id=cust1_id,
        parlo_user_id=staff.id,
        spot_id=spot.id,
        service_type_id=svc.id,
        start_time=yesterday.replace(hour=10, minute=0, second=0, microsecond=0),
        end_time=yesterday.replace(hour=10, minute=30, second=0, microsecond=0),
        status=AppointmentStatus.COMPLETED.value,
        source=AppointmentSource.WHATSAPP.value,
    )

    future_apt = Appointment(
        id=uuid4(),
        organization_id=org.id,
        location_id=loc.id,
        end_customer_id=cust2_id,
        parlo_user_id=staff.id,
        spot_id=spot.id,
        service_type_id=svc.id,
        start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=10, minute=30, second=0, microsecond=0),
        status=AppointmentStatus.CONFIRMED.value,
        source=AppointmentSource.WHATSAPP.value,
    )

    db.add_all([past_apt, future_apt])
    await db.flush()

    data.update({
        "customer1": cust1,
        "customer2": cust2,
        "past_appointment": past_apt,
        "future_appointment": future_apt,
    })
    return data
