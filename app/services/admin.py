"""Admin service - business logic for admin operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Appointment,
    Conversation,
    Customer,
    Location,
    Message,
    Organization,
    Staff,
)
from app.utils.jwt import create_access_token


async def get_admin_stats(db: AsyncSession) -> dict:
    """Get platform-wide statistics."""
    # Organizations by status
    org_counts = await db.execute(
        select(Organization.status, func.count()).group_by(Organization.status)
    )
    org_stats = {str(status): count for status, count in org_counts.all()}

    # Appointments by status
    appt_counts = await db.execute(
        select(Appointment.status, func.count()).group_by(Appointment.status)
    )
    appt_stats = {str(status): count for status, count in appt_counts.all()}

    # Total customers
    customer_count = await db.execute(select(func.count()).select_from(Customer))

    # Total messages
    message_count = await db.execute(select(func.count()).select_from(Message))

    return {
        "organizations": {
            "total": sum(org_stats.values()),
            "active": org_stats.get("active", 0),
            "onboarding": org_stats.get("onboarding", 0),
            "suspended": org_stats.get("suspended", 0),
            "churned": org_stats.get("churned", 0),
        },
        "appointments": {
            "total": sum(appt_stats.values()),
            "pending": appt_stats.get("pending", 0),
            "confirmed": appt_stats.get("confirmed", 0),
            "completed": appt_stats.get("completed", 0),
            "cancelled": appt_stats.get("cancelled", 0),
            "no_show": appt_stats.get("no_show", 0),
        },
        "customers_total": customer_count.scalar_one(),
        "messages_total": message_count.scalar_one(),
    }


async def list_organizations(
    db: AsyncSession,
    search: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Organization]:
    """List all organizations with optional filters."""
    query = select(Organization)

    if search:
        query = query.where(
            Organization.name.ilike(f"%{search}%")
            | Organization.phone_number.ilike(f"%{search}%")
        )

    if status:
        query = query.where(Organization.status == status)

    query = query.order_by(Organization.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_organization_detail(db: AsyncSession, org_id: UUID) -> dict | None:
    """Get organization with counts."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        return None

    # Get counts
    loc_count = await db.execute(
        select(func.count())
        .select_from(Location)
        .where(Location.organization_id == org_id)
    )
    staff_count = await db.execute(
        select(func.count()).select_from(Staff).where(Staff.organization_id == org_id)
    )
    cust_count = await db.execute(
        select(func.count())
        .select_from(Customer)
        .where(Customer.organization_id == org_id)
    )
    appt_count = await db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.organization_id == org_id)
    )

    return {
        "organization": org,
        "location_count": loc_count.scalar_one(),
        "staff_count": staff_count.scalar_one(),
        "customer_count": cust_count.scalar_one(),
        "appointment_count": appt_count.scalar_one(),
    }


async def update_organization_status(
    db: AsyncSession, org_id: UUID, new_status: str
) -> Organization | None:
    """Update organization status (suspend/reactivate)."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org:
        org.status = new_status
        await db.flush()
        await db.refresh(org)
    return org


def generate_impersonation_token(org_id: UUID) -> str:
    """Generate a JWT token for logging in as an organization."""
    return create_access_token(org_id)


async def list_conversations(
    db: AsyncSession,
    org_id: UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    """List conversations with org and customer info."""
    query = (
        select(Conversation)
        .options(
            selectinload(Conversation.organization),
            selectinload(Conversation.customer),
        )
        .order_by(Conversation.last_message_at.desc().nullslast())
    )

    if org_id:
        query = query.where(Conversation.organization_id == org_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    conversations = result.scalars().all()

    # Get message counts
    output = []
    for conv in conversations:
        msg_count = await db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conv.id)
        )
        output.append(
            {
                "conversation": conv,
                "message_count": msg_count.scalar_one(),
            }
        )

    return output


async def get_conversation_with_messages(
    db: AsyncSession, conversation_id: UUID
) -> dict | None:
    """Get conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.organization),
            selectinload(Conversation.customer),
            selectinload(Conversation.messages),
        )
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return None

    return {
        "conversation": conv,
        "messages": sorted(conv.messages, key=lambda m: m.created_at),
    }


async def get_activity_feed(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Get recent activity across all organizations."""
    # Recent organizations created
    orgs_result = await db.execute(
        select(Organization).order_by(Organization.created_at.desc()).limit(20)
    )
    org_activities = [
        {
            "id": org.id,
            "timestamp": org.created_at,
            "organization_id": org.id,
            "organization_name": org.name,
            "action_type": "org_created",
            "details": {"status": str(org.status)},
        }
        for org in orgs_result.scalars().all()
    ]

    # Recent appointments
    appts_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.organization))
        .order_by(Appointment.created_at.desc())
        .limit(30)
    )
    appt_activities = [
        {
            "id": appt.id,
            "timestamp": appt.created_at,
            "organization_id": appt.organization_id,
            "organization_name": appt.organization.name,
            "action_type": f"appointment_{appt.status}",
            "details": {
                "status": str(appt.status),
                "source": str(appt.source) if appt.source else None,
                "scheduled_start": appt.scheduled_start.isoformat()
                if appt.scheduled_start
                else None,
            },
        }
        for appt in appts_result.scalars().all()
    ]

    # Combine and sort
    all_activities = org_activities + appt_activities
    all_activities.sort(key=lambda x: x["timestamp"], reverse=True)

    return all_activities[:limit]
