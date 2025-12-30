#!/usr/bin/env python3
"""Setup initial organization data in the database.

This script creates the basic organization structure needed for WhatsApp integration.
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.organization import Organization
from app.models.location import Location
from app.models.spot import Spot
from app.models.service_type import ServiceType
from app.models.staff import Staff

settings = get_settings()


async def setup_organization():
    """Create initial organization with basic data."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Create organization
            org = Organization(
                id=uuid4(),
                name="YumeTesting",
                phone_country_code="+1",
                phone_number="+15550441129",
                whatsapp_phone_number_id="190530860803796",
                whatsapp_waba_id="",  # Will be populated from first webhook
                timezone="America/Mexico_City",
            )
            session.add(org)
            await session.flush()

            print(f"✅ Created organization: {org.name} (ID: {org.id})")

            # Create location
            location = Location(
                id=uuid4(),
                organization_id=org.id,
                name="Main Location",
                address="Test Address",
            )
            session.add(location)
            await session.flush()

            print(f"✅ Created location: {location.name} (ID: {location.id})")

            # Create spots (service stations)
            spots = []
            for i in range(1, 4):
                spot = Spot(
                    id=uuid4(),
                    location_id=location.id,
                    name=f"Spot {i}",
                    is_active=True,
                )
                session.add(spot)
                spots.append(spot)

            await session.flush()
            print(f"✅ Created {len(spots)} spots")

            # Create service types
            services = [
                ("Haircut", 30, 15000),  # $150.00 MXN
                ("Beard Trim", 15, 7500),  # $75.00 MXN
                ("Hair Color", 60, 30000),  # $300.00 MXN
            ]

            for name, duration, price_cents in services:
                service = ServiceType(
                    id=uuid4(),
                    organization_id=org.id,
                    name=name,
                    duration_minutes=duration,
                    price_cents=price_cents,
                    currency="MXN",
                )
                session.add(service)

            await session.flush()
            print(f"✅ Created {len(services)} service types")

            # Create owner/staff member
            staff = Staff(
                id=uuid4(),
                organization_id=org.id,
                name="Test Owner",
                phone_number="+15550199999",  # Different number for staff
                role="owner",
                is_active=True,
            )
            session.add(staff)
            await session.flush()

            print(f"✅ Created staff member: {staff.name} (ID: {staff.id})")

            # Commit everything
            await session.commit()

            print("\n" + "=" * 80)
            print("🎉 Organization setup complete!")
            print("=" * 80)
            print(f"\nOrganization ID: {org.id}")
            print(f"Location ID: {location.id}")
            print(f"Phone Number ID: {org.whatsapp_phone_number_id}")
            print(f"\nYou can now receive WhatsApp messages!")
            print("\nTo test, send a message to your WhatsApp test number from Meta.")

        except Exception as e:
            await session.rollback()
            print(f"❌ Error setting up organization: {e}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(setup_organization())
