"""Seed test data for local WhatsApp webhook testing.

This script creates:
- Test organization with WhatsApp connection
- Test location
- Test staff member (for staff routing tests)
- Test service type

Run this after creating the database schema with Alembic.

Usage:
    python scripts/seed_test_data.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import Location, Organization, OrganizationStatus, ServiceType, YumeUser
from app.schemas.organization import OrganizationCreate
from app.schemas.service_type import ServiceTypeCreate
from app.schemas.staff import StaffCreate
from app.services import organization as org_service
from app.services import service_type as service_service
from app.services import staff as staff_service


# Test data constants (matching test_webhook.py)
TEST_PHONE_NUMBER_ID = "test_phone_123"
TEST_WABA_ID = "test_waba_123"
TEST_ORG_NAME = "Test Salon"
TEST_STAFF_PHONE = "525512345678"
TEST_STAFF_NAME = "Pedro González"


async def seed_data():
    """Seed test data for webhook testing."""
    async with async_session_maker() as db:
        try:
            print("🌱 Starting test data seeding...")
            print("=" * 80)

            # Check if organization already exists
            existing_org = await org_service.get_organization_by_whatsapp_phone_id(
                db, TEST_PHONE_NUMBER_ID
            )

            if existing_org:
                print(f"✅ Organization already exists: {existing_org.name} (ID: {existing_org.id})")
                org = existing_org
            else:
                # Create test organization
                print(f"\n📍 Creating organization: {TEST_ORG_NAME}")
                org_data = OrganizationCreate(
                    name=TEST_ORG_NAME,
                    phone_country_code="+52",
                    phone_number="5512345678",
                    timezone="America/Mexico_City",
                    settings={"test_mode": True},
                )
                org = await org_service.create_organization(db, org_data)

                # Connect WhatsApp
                from app.schemas.organization import OrganizationConnectWhatsApp

                whatsapp_data = OrganizationConnectWhatsApp(
                    whatsapp_phone_number_id=TEST_PHONE_NUMBER_ID,
                    whatsapp_waba_id=TEST_WABA_ID,
                )
                org = await org_service.connect_whatsapp(db, org, whatsapp_data)
                print(f"  ✅ Created organization: {org.name} (ID: {org.id})")
                print(f"  📱 WhatsApp phone_number_id: {org.whatsapp_phone_number_id}")

            # Create location if it doesn't exist
            from sqlalchemy import select

            location_result = await db.execute(
                select(Location).where(
                    Location.organization_id == org.id,
                    Location.is_primary == True,
                )
            )
            location = location_result.scalar_one_or_none()

            if location:
                print(f"✅ Location already exists: {location.name} (ID: {location.id})")
            else:
                print(f"\n📍 Creating primary location")
                location = Location(
                    organization_id=org.id,
                    name="Main Location",
                    address="Calle Falsa 123, CDMX",
                    is_primary=True,
                    business_hours={
                        "mon": {"open": "10:00", "close": "20:00"},
                        "tue": {"open": "10:00", "close": "20:00"},
                        "wed": {"open": "10:00", "close": "20:00"},
                        "thu": {"open": "10:00", "close": "20:00"},
                        "fri": {"open": "10:00", "close": "20:00"},
                        "sat": {"open": "10:00", "close": "18:00"},
                        "sun": {"open": "closed", "close": "closed"},
                    },
                )
                db.add(location)
                await db.flush()
                await db.refresh(location)
                print(f"  ✅ Created location: {location.name} (ID: {location.id})")

            # Create staff member if doesn't exist
            existing_staff = await staff_service.get_staff_by_phone(
                db, org.id, TEST_STAFF_PHONE
            )

            if existing_staff:
                print(
                    f"✅ Staff member already exists: {existing_staff.name} (ID: {existing_staff.id})"
                )
                staff = existing_staff
            else:
                print(f"\n👨‍💼 Creating staff member: {TEST_STAFF_NAME}")
                staff_data = StaffCreate(
                    name=TEST_STAFF_NAME,
                    phone_number=TEST_STAFF_PHONE,
                    role="owner",
                    location_id=location.id,
                    is_active=True,
                    permissions={
                        "can_view_schedule": True,
                        "can_book": True,
                        "can_cancel": True,
                        "can_view_reports": True,
                    },
                    settings={"test_mode": True},
                )
                staff = await staff_service.create_staff(db, org.id, staff_data)
                print(f"  ✅ Created staff: {staff.name} (ID: {staff.id})")
                print(f"  📱 Phone number: {staff.phone_number}")
                print(
                    f"  🔑 This phone will be recognized as STAFF in message routing"
                )

            # Create service type if doesn't exist
            from sqlalchemy import select

            service_result = await db.execute(
                select(ServiceType).where(
                    ServiceType.organization_id == org.id,
                    ServiceType.name == "Corte de cabello",
                )
            )
            service = service_result.scalar_one_or_none()

            if service:
                print(f"✅ Service type already exists: {service.name} (ID: {service.id})")
            else:
                print(f"\n💇 Creating service type: Corte de cabello")
                service_data = ServiceTypeCreate(
                    name="Corte de cabello",
                    description="Corte de cabello para caballero",
                    duration_minutes=30,
                    price_cents=15000,  # $150.00 MXN
                    currency="MXN",
                    is_active=True,
                    settings={"requires_deposit": False},
                )
                service = await service_service.create_service_type(
                    db, org.id, service_data
                )
                print(f"  ✅ Created service: {service.name} (ID: {service.id})")
                print(f"  ⏱️  Duration: {service.duration_minutes} minutes")
                print(f"  💰 Price: ${service.price_cents / 100:.2f} {service.currency}")

            # Commit all changes
            await db.commit()

            print("\n" + "=" * 80)
            print("✅ Test data seeding complete!")
            print("=" * 80)
            print("\n📋 Summary:")
            print(f"  Organization: {org.name} (ID: {org.id})")
            print(f"  WhatsApp ID: {org.whatsapp_phone_number_id}")
            print(f"  Location: {location.name} (ID: {location.id})")
            print(f"  Staff: {staff.name} - {staff.phone_number} (ID: {staff.id})")
            print(f"  Service: {service.name} (ID: {service.id})")
            print("\n🧪 Ready for testing!")
            print("\nYou can now test with:")
            print(
                f"  Customer: python scripts/test_webhook.py --customer 'Hola' --phone '525587654321'"
            )
            print(
                f"  Staff: python scripts/test_webhook.py --staff 'Qué tengo hoy?' --phone '{TEST_STAFF_PHONE}'"
            )

        except Exception as e:
            print(f"\n❌ Error seeding data: {e}")
            await db.rollback()
            import traceback

            traceback.print_exc()
            sys.exit(1)


async def clean_test_data():
    """Clean up test data (useful for resetting tests)."""
    async with async_session_maker() as db:
        try:
            print("🧹 Cleaning test data...")

            org = await org_service.get_organization_by_whatsapp_phone_id(
                db, TEST_PHONE_NUMBER_ID
            )

            if org:
                print(f"Deleting organization: {org.name}")
                # SQLAlchemy will cascade delete all related data
                await db.delete(org)
                await db.commit()
                print("✅ Test data cleaned")
            else:
                print("No test data found")

        except Exception as e:
            print(f"❌ Error cleaning data: {e}")
            await db.rollback()
            sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed test data for webhook testing")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean test data instead of seeding",
    )

    args = parser.parse_args()

    if args.clean:
        asyncio.run(clean_test_data())
    else:
        asyncio.run(seed_data())
