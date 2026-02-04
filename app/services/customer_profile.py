"""Customer profile service for cross-business lookup and profile management.

This service enables the "returning customer" experience where we can:
1. Look up existing customer info from other businesses (by phone)
2. Prefill known information (name, preferences)
3. Track when info was last verified
4. Build incremental customer profiles over time

Privacy considerations:
- Only basic info (name) is shared across businesses
- Detailed preferences stay within each business's customer record
- Phone number is the only cross-business identifier
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, EndCustomer, ServiceType

logger = logging.getLogger(__name__)

# How long before we ask to re-confirm known info (30 days)
RECONFIRM_THRESHOLD_DAYS = 30


async def get_customer_by_phone(
    db: AsyncSession,
    organization_id: UUID,
    phone_number: str,
) -> EndCustomer | None:
    """Get a customer by phone number for a specific organization.

    Args:
        db: Database session
        organization_id: Organization ID
        phone_number: Customer's phone number

    Returns:
        Customer if found, None otherwise
    """
    result = await db.execute(
        select(EndCustomer).where(
            EndCustomer.organization_id == organization_id,
            EndCustomer.phone_number == phone_number,
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_customer(
    db: AsyncSession,
    organization_id: UUID,
    phone_number: str,
    name: str | None = None,
) -> EndCustomer:
    """Get existing customer or create new one, with cross-business lookup.

    If this is a new customer for this business but they exist at another
    business, we'll prefill their name (if available).

    Args:
        db: Database session
        organization_id: Organization ID
        phone_number: Customer's phone number
        name: Optional name to set

    Returns:
        Customer record (existing or new)
    """
    # Check if customer exists for this org
    customer = await get_customer_by_phone(db, organization_id, phone_number)

    if customer:
        # Update name if provided and we don't have one
        if name and not customer.name:
            customer.name = name
            await db.flush()
        return customer

    # New customer for this org - check if they exist elsewhere
    cross_business_info = await lookup_cross_business_profile(db, phone_number)

    # Create new customer
    customer = EndCustomer(
        organization_id=organization_id,
        phone_number=phone_number,
        name=name or cross_business_info.get("name"),
        profile_data={
            "source": "cross_business" if cross_business_info.get("name") else "new",
        },
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)

    logger.info(
        f"Created new customer: {customer.id}, "
        f"cross_business_name: {cross_business_info.get('name')}"
    )

    return customer


async def lookup_cross_business_profile(
    db: AsyncSession,
    phone_number: str,
) -> dict[str, Any]:
    """Look up customer info from other businesses.

    This finds the most complete profile for a phone number across
    all businesses. Only basic info (name) is shared.

    Args:
        db: Database session
        phone_number: Customer's phone number

    Returns:
        Dict with cross-business profile info (name, appointment_count, etc.)
    """
    # Find all customers with this phone number
    result = await db.execute(
        select(EndCustomer).where(
            EndCustomer.phone_number == phone_number,
            EndCustomer.name.isnot(None),  # Only customers with names
        ).order_by(
            EndCustomer.name_verified_at.desc().nullslast(),  # Prefer verified names
            EndCustomer.updated_at.desc(),  # Then most recently updated
        )
    )
    customers = result.scalars().all()

    if not customers:
        return {}

    # Use the best available name (verified > most recent)
    best_customer = customers[0]

    # Count total appointments across businesses
    total_appointments = 0
    for customer in customers:
        # Get appointment count for each customer record
        apt_result = await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.customer_id == customer.id
            )
        )
        total_appointments += apt_result.scalar() or 0

    return {
        "name": best_customer.name,
        "name_verified": best_customer.name_verified_at is not None,
        "businesses_count": len(customers),
        "total_appointments": total_appointments,
        "last_seen": max(c.updated_at for c in customers).isoformat(),
    }


async def update_customer_name(
    db: AsyncSession,
    customer: EndCustomer,
    name: str,
    verified: bool = False,
) -> EndCustomer:
    """Update customer's name, optionally marking as verified.

    Args:
        db: Database session
        customer: Customer to update
        name: New name
        verified: Whether the customer confirmed this name

    Returns:
        Updated customer
    """
    customer.name = name

    if verified:
        customer.name_verified_at = datetime.now(timezone.utc)

    await db.flush()

    logger.info(
        f"Updated customer name: {customer.id}, verified: {verified}"
    )

    return customer


async def should_reconfirm_info(customer: EndCustomer) -> bool:
    """Check if we should ask the customer to reconfirm their info.

    We reconfirm if:
    1. Name was never verified
    2. Name was verified more than RECONFIRM_THRESHOLD_DAYS ago

    Args:
        customer: Customer to check

    Returns:
        True if we should ask to reconfirm
    """
    if not customer.name:
        return True  # No name at all

    if not customer.name_verified_at:
        return True  # Name not verified

    threshold = datetime.now(timezone.utc) - timedelta(days=RECONFIRM_THRESHOLD_DAYS)
    return customer.name_verified_at < threshold


async def update_customer_profile(
    db: AsyncSession,
    customer: EndCustomer,
    profile_updates: dict[str, Any],
) -> EndCustomer:
    """Update customer's profile data.

    Args:
        db: Database session
        customer: Customer to update
        profile_updates: Dict of profile fields to update

    Returns:
        Updated customer
    """
    current_profile = dict(customer.profile_data or {})
    current_profile.update(profile_updates)
    customer.profile_data = current_profile

    await db.flush()

    return customer


async def record_service_usage(
    db: AsyncSession,
    customer: EndCustomer,
    service: ServiceType,
) -> None:
    """Record that a customer used a service, for preference learning.

    Args:
        db: Database session
        customer: Customer
        service: Service used
    """
    profile = dict(customer.profile_data or {})

    # Track last services (keep most recent 5)
    last_services = profile.get("last_services", [])
    if service.name not in last_services:
        last_services.insert(0, service.name)
        last_services = last_services[:5]  # Keep only 5 most recent
        profile["last_services"] = last_services

    customer.profile_data = profile
    await db.flush()


async def get_customer_preferences(
    db: AsyncSession,
    customer: EndCustomer,
) -> dict[str, Any]:
    """Get customer's preferences for personalization.

    This analyzes the customer's history to determine preferences:
    - Preferred appointment times (morning, afternoon, evening)
    - Preferred days of week
    - Frequently used services

    Args:
        db: Database session
        customer: Customer

    Returns:
        Dict of preferences
    """
    from app.models import AppointmentStatus

    # Get completed appointments
    result = await db.execute(
        select(Appointment).where(
            Appointment.customer_id == customer.id,
            Appointment.status == AppointmentStatus.COMPLETED.value,
        ).order_by(Appointment.scheduled_start.desc()).limit(20)
    )
    appointments = result.scalars().all()

    if not appointments:
        return customer.profile_data.get("preferences", {})

    # Analyze times
    morning_count = 0  # Before 12 PM
    afternoon_count = 0  # 12 PM - 5 PM
    evening_count = 0  # After 5 PM

    day_counts = {}

    for apt in appointments:
        hour = apt.scheduled_start.hour

        if hour < 12:
            morning_count += 1
        elif hour < 17:
            afternoon_count += 1
        else:
            evening_count += 1

        day_name = apt.scheduled_start.strftime("%A").lower()
        day_counts[day_name] = day_counts.get(day_name, 0) + 1

    # Determine preferred time of day
    total = morning_count + afternoon_count + evening_count
    preferred_times = []
    if morning_count / total > 0.4:
        preferred_times.append("morning")
    if afternoon_count / total > 0.4:
        preferred_times.append("afternoon")
    if evening_count / total > 0.4:
        preferred_times.append("evening")

    # Determine preferred days (if pattern exists)
    preferred_days = [
        day for day, count in day_counts.items()
        if count >= 2  # At least 2 visits on this day
    ]

    return {
        "preferred_times": preferred_times,
        "preferred_days": preferred_days,
        "appointment_count": len(appointments),
    }


def format_customer_context_for_ai(
    customer: EndCustomer,
    preferences: dict[str, Any] | None = None,
    cross_business: dict[str, Any] | None = None,
) -> str:
    """Format customer information for AI system prompt.

    Args:
        customer: Customer
        preferences: Customer preferences (from get_customer_preferences)
        cross_business: Cross-business info (from lookup_cross_business_profile)

    Returns:
        Formatted string for system prompt
    """
    lines = []

    # Basic info
    lines.append(f"- Teléfono: {customer.phone_number}")

    if customer.name:
        verified = " (verificado)" if customer.name_verified_at else ""
        lines.append(f"- Nombre: {customer.name}{verified}")
    else:
        lines.append("- Nombre: No proporcionado")

    # Cross-business context
    if cross_business and cross_business.get("businesses_count", 0) > 1:
        lines.append(f"- Ha visitado {cross_business['businesses_count']} negocios")
        lines.append(f"- Total de citas previas: {cross_business['total_appointments']}")

    # Preferences
    if preferences:
        if preferences.get("preferred_times"):
            times_str = ", ".join(preferences["preferred_times"])
            lines.append(f"- Prefiere: {times_str}")
        if preferences.get("preferred_days"):
            days_str = ", ".join(preferences["preferred_days"])
            lines.append(f"- Días preferidos: {days_str}")

    # Last services from profile
    profile = customer.profile_data or {}
    if profile.get("last_services"):
        services_str = ", ".join(profile["last_services"][:3])
        lines.append(f"- Últimos servicios: {services_str}")

    return "\n".join(lines)
