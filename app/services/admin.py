"""Admin service - business logic for admin operations."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Appointment,
    Conversation,
    Customer,
    FunctionTrace,
    Location,
    Message,
    OnboardingSession,
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
            selectinload(Conversation.end_customer),
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
            selectinload(Conversation.end_customer),
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


async def delete_organization(db: AsyncSession, org_id: UUID) -> bool:
    """Permanently delete an organization and all associated data.

    Note: OnboardingSession.organization_id is a STRING field, not a FK,
    so it doesn't cascade automatically. We delete it manually first.
    We also delete by phone number to catch incomplete sessions (where org_id is NULL).
    All other entities have proper FK cascades and will be deleted automatically.
    """
    # 1. Get staff phone numbers before deletion (for cleaning up incomplete sessions)
    staff_result = await db.execute(
        select(Staff.phone_number).where(Staff.organization_id == org_id)
    )
    staff_phones = [row[0] for row in staff_result.fetchall()]

    # 2. Delete OnboardingSession records by organization_id (completed sessions)
    await db.execute(
        delete(OnboardingSession).where(OnboardingSession.organization_id == str(org_id))
    )

    # 3. Delete OnboardingSession records by phone number (catches incomplete sessions)
    if staff_phones:
        await db.execute(
            delete(OnboardingSession).where(
                OnboardingSession.phone_number.in_(staff_phones)
            )
        )

    # 4. Delete Organization (cascades to all other entities via FK ondelete="CASCADE")
    result = await db.execute(delete(Organization).where(Organization.id == org_id))

    await db.commit()
    return result.rowcount > 0


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


# =============================================================================
# Logs / Function Traces
# =============================================================================


async def list_correlation_summaries(
    db: AsyncSession,
    phone_number: str | None = None,
    organization_id: UUID | None = None,
    errors_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """List correlation summaries (grouped traces).

    Returns a list of correlation summaries with metadata and total count.
    """
    from sqlalchemy import distinct

    # Build base query for distinct correlation IDs
    base_query = select(FunctionTrace.correlation_id).distinct()

    if phone_number:
        base_query = base_query.where(FunctionTrace.phone_number == phone_number)

    if organization_id:
        base_query = base_query.where(FunctionTrace.organization_id == organization_id)

    if errors_only:
        # Get correlations that have at least one error
        error_corrs = select(FunctionTrace.correlation_id).where(
            FunctionTrace.is_error == True
        ).distinct()
        base_query = base_query.where(FunctionTrace.correlation_id.in_(error_corrs))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_query)).scalar_one()

    # Get paginated correlation IDs (ordered by most recent first)
    # We need to get the min created_at for each correlation to order properly
    corr_query = (
        select(
            FunctionTrace.correlation_id,
            func.min(FunctionTrace.created_at).label("started_at"),
        )
        .group_by(FunctionTrace.correlation_id)
    )

    if phone_number:
        corr_query = corr_query.where(FunctionTrace.phone_number == phone_number)
    if organization_id:
        corr_query = corr_query.where(FunctionTrace.organization_id == organization_id)
    if errors_only:
        corr_query = corr_query.having(func.max(FunctionTrace.is_error.cast(Integer)) == 1)

    corr_query = corr_query.order_by(func.min(FunctionTrace.created_at).desc())
    corr_query = corr_query.offset(skip).limit(limit)

    from sqlalchemy import Integer

    result = await db.execute(corr_query)
    correlation_rows = result.all()

    # Build summaries for each correlation
    summaries = []
    for corr_id, started_at in correlation_rows:
        # Get all traces for this correlation
        traces_result = await db.execute(
            select(FunctionTrace)
            .where(FunctionTrace.correlation_id == corr_id)
            .order_by(FunctionTrace.sequence_number)
        )
        traces = list(traces_result.scalars().all())

        if not traces:
            continue

        first_trace = traces[0]
        total_duration = sum(t.duration_ms for t in traces)
        has_errors = any(t.is_error for t in traces)

        # Get organization name if we have an org ID
        org_name = None
        if first_trace.organization_id:
            org_result = await db.execute(
                select(Organization.name).where(
                    Organization.id == first_trace.organization_id
                )
            )
            org_name = org_result.scalar_one_or_none()

        summaries.append({
            "correlation_id": corr_id,
            "phone_number": first_trace.phone_number,
            "organization_id": first_trace.organization_id,
            "organization_name": org_name,
            "started_at": started_at,
            "total_duration_ms": total_duration,
            "trace_count": len(traces),
            "has_errors": has_errors,
            "entry_function": first_trace.function_name,
        })

    return summaries, total_count


async def get_correlation_detail(
    db: AsyncSession, correlation_id: UUID
) -> dict | None:
    """Get all traces for a correlation."""
    traces_result = await db.execute(
        select(FunctionTrace)
        .where(FunctionTrace.correlation_id == correlation_id)
        .order_by(FunctionTrace.sequence_number)
    )
    traces = list(traces_result.scalars().all())

    if not traces:
        return None

    first_trace = traces[0]
    total_duration = sum(t.duration_ms for t in traces)
    has_errors = any(t.is_error for t in traces)

    # Get organization name
    org_name = None
    if first_trace.organization_id:
        org_result = await db.execute(
            select(Organization.name).where(
                Organization.id == first_trace.organization_id
            )
        )
        org_name = org_result.scalar_one_or_none()

    return {
        "correlation_id": correlation_id,
        "phone_number": first_trace.phone_number,
        "organization_id": first_trace.organization_id,
        "organization_name": org_name,
        "started_at": first_trace.created_at,
        "total_duration_ms": total_duration,
        "trace_count": len(traces),
        "has_errors": has_errors,
        "entry_function": first_trace.function_name,
        "traces": [
            {
                "id": t.id,
                "sequence_number": t.sequence_number,
                "function_name": t.function_name,
                "module_path": t.module_path,
                "trace_type": t.trace_type,
                "duration_ms": t.duration_ms,
                "is_error": t.is_error,
                "input_summary": t.input_summary,
                "output_summary": t.output_summary,
                "error_type": t.error_type,
                "error_message": t.error_message,
                "created_at": t.created_at,
            }
            for t in traces
        ],
    }


async def get_trace_detail(db: AsyncSession, trace_id: UUID) -> dict | None:
    """Get a single trace by ID."""
    result = await db.execute(
        select(FunctionTrace).where(FunctionTrace.id == trace_id)
    )
    trace = result.scalar_one_or_none()

    if not trace:
        return None

    return {
        "id": trace.id,
        "correlation_id": trace.correlation_id,
        "sequence_number": trace.sequence_number,
        "function_name": trace.function_name,
        "module_path": trace.module_path,
        "trace_type": trace.trace_type,
        "duration_ms": trace.duration_ms,
        "is_error": trace.is_error,
        "input_summary": trace.input_summary,
        "output_summary": trace.output_summary,
        "error_type": trace.error_type,
        "error_message": trace.error_message,
        "phone_number": trace.phone_number,
        "organization_id": trace.organization_id,
        "created_at": trace.created_at,
    }
