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

    All related entities (Staff, Location, Appointments, etc.) are deleted
    automatically via FK cascades defined in the models.
    """
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


# =============================================================================
# User Activity Feed
# =============================================================================


def _derive_flow_type(traces: list) -> tuple[str, str]:
    """Derive flow type and label from function names in trace chain."""
    func_names = {t.function_name for t in traces}
    module_paths = {t.module_path for t in traces}

    if "handle_customer_message" in func_names or "_handle_end_customer" in func_names:
        return "customer", "Customer Booking"
    if "_handle_staff_onboarding" in func_names:
        return "staff_onboarding", "Staff Onboarding"
    if "handle_staff_message" in func_names or "_handle_business_management" in func_names:
        return "staff", "Business Management"
    if "_handle_business_onboarding" in func_names or any(
        "onboarding" in m for m in module_paths
    ):
        return "onboarding", "Business Onboarding"
    if "_route_central_number_message" in func_names:
        return "central", "Central Number"

    return "unknown", "Unknown"


def _derive_flow_status(flow_type: str, ai_tools: list[str]) -> str | None:
    """Derive a human-readable flow status from the last AI tool called."""
    ONBOARDING_TOOLS = {
        "save_business_info": "Gathering business info",
        "add_service": "Adding services",
        "get_current_menu": "Reviewing menu",
        "add_staff_member": "Adding staff",
        "save_business_hours": "Setting hours",
        "provision_twilio_number": "Provisioning WhatsApp",
        "complete_onboarding": "Completing setup",
        "send_dashboard_link": "Sending dashboard link",
    }
    CUSTOMER_TOOLS = {
        "check_availability": "Checking availability",
        "book_appointment": "Booking appointment",
        "cancel_appointment": "Cancelling appointment",
        "reschedule_appointment": "Rescheduling",
    }
    STAFF_TOOLS = {
        "get_schedule": "Viewing schedule",
        "block_time": "Blocking time",
        "mark_complete": "Marking complete",
        "book_walk_in": "Booking walk-in",
    }

    tool_maps = {
        "onboarding": ONBOARDING_TOOLS,
        "customer": CUSTOMER_TOOLS,
        "staff": STAFF_TOOLS,
    }

    tool_map = tool_maps.get(flow_type)
    if tool_map is None:
        return None

    # Check last tool first, then earlier ones
    for tool_name in reversed(ai_tools):
        if tool_name in tool_map:
            return tool_map[tool_name]

    return "Chatting"


def _extract_message_preview(traces: list) -> str | None:
    """Extract inbound message content from handle_*_message input_summary."""
    handler_names = {
        "handle_customer_message",
        "handle_staff_message",
        "handle_message",
    }
    for t in traces:
        if t.function_name in handler_names and t.input_summary:
            # input_summary captures all args; look for message_content
            msg = t.input_summary.get("message_content")
            if msg and isinstance(msg, str):
                return msg[:200]
    return None


def _extract_response_preview(traces: list) -> str | None:
    """Extract AI response text from handle_*_message output_summary."""
    handler_names = {
        "handle_customer_message",
        "handle_staff_message",
        "handle_message",
    }
    for t in traces:
        if t.function_name in handler_names and t.output_summary:
            val = t.output_summary.get("_value")
            if val and isinstance(val, str):
                return val[:200]
    return None


def _extract_ai_tools(traces: list) -> list[str]:
    """Extract AI tool names from ai_tool type traces."""
    tools = []
    for t in traces:
        if t.trace_type == "ai_tool" or t.function_name == "_execute_tool":
            tool_name = None
            if t.input_summary:
                tool_name = t.input_summary.get("tool_name")
            if tool_name and tool_name not in tools:
                tools.append(tool_name)
    return tools


def _extract_error_summary(traces: list) -> str | None:
    """Get first error message from traces."""
    for t in traces:
        if t.is_error and t.error_message:
            return t.error_message[:200]
    return None


def _enrich_correlation(
    correlation_id: UUID,
    traces: list,
) -> dict:
    """Enrich a single correlation with flow type, previews, tools."""
    flow_type, flow_label = _derive_flow_type(traces)
    message_preview = _extract_message_preview(traces)
    response_preview = _extract_response_preview(traces)
    ai_tools = _extract_ai_tools(traces)
    error_summary = _extract_error_summary(traces)
    flow_status = _derive_flow_status(flow_type, ai_tools)
    total_duration = sum(t.duration_ms for t in traces)
    has_errors = any(t.is_error for t in traces)

    return {
        "correlation_id": correlation_id,
        "started_at": traces[0].created_at,
        "total_duration_ms": total_duration,
        "trace_count": len(traces),
        "has_errors": has_errors,
        "flow_type": flow_type,
        "flow_label": flow_label,
        "message_preview": message_preview,
        "response_preview": response_preview,
        "ai_tools_used": ai_tools,
        "error_summary": error_summary,
        "flow_status": flow_status,
    }


async def list_user_activity_groups(
    db: AsyncSession,
    phone_number: str | None = None,
    organization_id: UUID | None = None,
    errors_only: bool = False,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """List user activity groups (phone numbers with enriched correlations).

    Returns groups sorted by most recent activity, paginated by phone number.
    """
    from collections import defaultdict
    from sqlalchemy import Integer

    # Step 1: Get distinct phone numbers ordered by latest activity
    phone_query = (
        select(
            FunctionTrace.phone_number,
            func.max(FunctionTrace.created_at).label("latest_activity"),
        )
        .where(FunctionTrace.phone_number.isnot(None))
        .group_by(FunctionTrace.phone_number)
    )

    if phone_number:
        phone_query = phone_query.where(
            FunctionTrace.phone_number.ilike(f"%{phone_number}%")
        )
    if organization_id:
        phone_query = phone_query.where(
            FunctionTrace.organization_id == organization_id
        )
    if errors_only:
        phone_query = phone_query.having(
            func.max(FunctionTrace.is_error.cast(Integer)) == 1
        )

    phone_query = phone_query.order_by(
        func.max(FunctionTrace.created_at).desc()
    )

    # Count total phone numbers
    count_subq = phone_query.subquery()
    count_result = await db.execute(
        select(func.count()).select_from(count_subq)
    )
    total_count = count_result.scalar_one()

    # Paginate phone numbers
    phone_query = phone_query.offset(skip).limit(limit)
    phone_result = await db.execute(phone_query)
    phone_rows = phone_result.all()

    if not phone_rows:
        return [], total_count

    phone_numbers = [row.phone_number for row in phone_rows]

    # Step 2: Get ALL traces for these phone numbers in one batch
    traces_query = (
        select(FunctionTrace)
        .where(FunctionTrace.phone_number.in_(phone_numbers))
        .order_by(FunctionTrace.created_at.desc(), FunctionTrace.sequence_number)
    )
    traces_result = await db.execute(traces_query)
    all_traces = list(traces_result.scalars().all())

    # Group traces: phone -> correlation_id -> [traces]
    phone_corr_map: dict[str, dict[UUID, list]] = defaultdict(lambda: defaultdict(list))
    for t in all_traces:
        phone_corr_map[t.phone_number][t.correlation_id].append(t)

    # Sort traces within each correlation by sequence_number
    for phone, corr_map in phone_corr_map.items():
        for corr_id, traces in corr_map.items():
            traces.sort(key=lambda t: t.sequence_number)

    # Step 3: Batch lookup org names
    org_ids = {t.organization_id for t in all_traces if t.organization_id}
    org_names: dict[UUID, str] = {}
    if org_ids:
        org_result = await db.execute(
            select(Organization.id, Organization.name).where(
                Organization.id.in_(org_ids)
            )
        )
        org_names = {row.id: row.name for row in org_result.all()}

    # Step 4: Build groups
    groups = []
    for phone, latest_activity in phone_rows:
        corr_map = phone_corr_map.get(phone, {})

        # Enrich each correlation
        enriched_corrs = []
        for corr_id, traces in corr_map.items():
            enriched_corrs.append(_enrich_correlation(corr_id, traces))

        # Sort by most recent first
        enriched_corrs.sort(key=lambda c: c["started_at"], reverse=True)

        # Determine primary flow type (most common)
        flow_counts: dict[str, int] = defaultdict(int)
        for c in enriched_corrs:
            flow_counts[c["flow_type"]] += 1
        primary_flow = max(flow_counts, key=flow_counts.get) if flow_counts else "unknown"
        flow_label_map = {
            "customer": "Customer Booking",
            "staff": "Business Management",
            "onboarding": "Business Onboarding",
            "staff_onboarding": "Staff Onboarding",
            "central": "Central Number",
            "unknown": "Unknown",
        }

        # Determine org info (from most recent trace)
        first_org_id = None
        first_org_name = None
        for t in all_traces:
            if t.phone_number == phone and t.organization_id:
                first_org_id = t.organization_id
                first_org_name = org_names.get(t.organization_id)
                break

        error_count = sum(1 for c in enriched_corrs if c["has_errors"])
        latest_msg = next(
            (c["message_preview"] for c in enriched_corrs if c["message_preview"]),
            None,
        )

        groups.append({
            "phone_number": phone,
            "organization_id": first_org_id,
            "organization_name": first_org_name,
            "latest_activity": latest_activity,
            "total_interactions": len(enriched_corrs),
            "error_count": error_count,
            "primary_flow_type": primary_flow,
            "primary_flow_label": flow_label_map.get(primary_flow, "Unknown"),
            "latest_message_preview": latest_msg,
            "correlations": enriched_corrs,
        })

    return groups, total_count


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


# =============================================================================
# Pending Numbers Management
# =============================================================================


async def list_pending_number_organizations(
    db: AsyncSession,
) -> list[Organization]:
    """List organizations waiting for WhatsApp number assignment.

    These are active orgs where settings.number_status == 'pending'.
    """
    from app.models import OrganizationStatus

    result = await db.execute(
        select(Organization)
        .where(
            Organization.status == OrganizationStatus.ACTIVE.value,
            Organization.settings["number_status"].astext == "pending",
        )
        .order_by(Organization.created_at.desc())
    )
    return list(result.scalars().all())


async def assign_whatsapp_number(
    db: AsyncSession,
    org_id: UUID,
    phone_number: str,
    sender_sid: str,
) -> Organization | None:
    """Manually assign a WhatsApp number to an organization.

    Args:
        db: Database session
        org_id: Organization ID
        phone_number: WhatsApp phone number (E.164 format)
        sender_sid: Twilio sender SID

    Returns:
        Updated organization or None if not found
    """
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()

    if not org:
        return None

    # Update org settings with assigned number
    settings_dict = dict(org.settings or {})
    settings_dict["number_status"] = "active"
    settings_dict["whatsapp_ready"] = True
    settings_dict["twilio_phone_number"] = phone_number
    settings_dict["twilio_sender_sid"] = sender_sid
    settings_dict["whatsapp_provider"] = "twilio"

    org.settings = settings_dict
    org.whatsapp_phone_number_id = phone_number

    await db.flush()
    await db.refresh(org)

    return org
