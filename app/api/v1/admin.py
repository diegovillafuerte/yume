"""Admin API endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import require_admin
from app.api.deps import get_db
from app.config import get_settings
from app.schemas.admin import (
    AdminActivityItem,
    AdminConversationDetail,
    AdminConversationSummary,
    AdminImpersonateResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMessageDetail,
    AdminOrganizationDetail,
    AdminOrganizationSummary,
    AdminOrgStatusUpdate,
    AdminStats,
)
from app.schemas.logs import (
    CorrelationDetail,
    CorrelationListResponse,
    CorrelationSummary,
    TraceItem,
)
from app.schemas.playground import (
    PlaygroundExchangeListResponse,
    PlaygroundSendRequest,
    PlaygroundSendResponse,
    PlaygroundTraceListResponse,
    PlaygroundUserDetail,
    PlaygroundUserSummary,
    TraceExchangeSummary,
    TraceStepDetail,
    TraceStepSummary,
)
from app.services import admin as admin_service
from app.services import playground as playground_service
from app.utils.jwt import create_admin_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# Auth
@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest) -> AdminLoginResponse:
    """Admin login with master password."""
    settings = get_settings()

    if not settings.admin_master_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access not configured",
        )

    if request.password != settings.admin_master_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    token = create_admin_access_token()

    return AdminLoginResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# Stats
@router.get("/stats", response_model=AdminStats, dependencies=[Depends(require_admin)])
async def get_stats(db: Annotated[AsyncSession, Depends(get_db)]) -> AdminStats:
    """Get platform-wide statistics."""
    stats = await admin_service.get_admin_stats(db)
    return AdminStats(**stats)


# Organizations
@router.get(
    "/organizations",
    response_model=list[AdminOrganizationSummary],
    dependencies=[Depends(require_admin)],
)
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AdminOrganizationSummary]:
    """List all organizations."""
    orgs = await admin_service.list_organizations(db, search, status, skip, limit)
    return [
        AdminOrganizationSummary(
            id=org.id,
            name=org.name,
            phone_number=org.phone_number,
            phone_country_code=org.phone_country_code,
            status=str(org.status),
            whatsapp_connected=bool(org.whatsapp_phone_number_id),
            created_at=org.created_at,
        )
        for org in orgs
    ]


@router.get(
    "/organizations/{org_id}",
    response_model=AdminOrganizationDetail,
    dependencies=[Depends(require_admin)],
)
async def get_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOrganizationDetail:
    """Get organization details."""
    data = await admin_service.get_organization_detail(db, org_id)
    if not data:
        raise HTTPException(status_code=404, detail="Organization not found")

    org = data["organization"]
    return AdminOrganizationDetail(
        id=org.id,
        name=org.name,
        phone_number=org.phone_number,
        phone_country_code=org.phone_country_code,
        status=str(org.status),
        whatsapp_connected=bool(org.whatsapp_phone_number_id),
        created_at=org.created_at,
        timezone=org.timezone,
        settings=org.settings or {},
        location_count=data["location_count"],
        staff_count=data["staff_count"],
        customer_count=data["customer_count"],
        appointment_count=data["appointment_count"],
    )


@router.post(
    "/organizations/{org_id}/impersonate",
    response_model=AdminImpersonateResponse,
    dependencies=[Depends(require_admin)],
)
async def impersonate_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminImpersonateResponse:
    """Generate a token to login as an organization."""
    data = await admin_service.get_organization_detail(db, org_id)
    if not data:
        raise HTTPException(status_code=404, detail="Organization not found")

    settings = get_settings()
    org = data["organization"]
    token = admin_service.generate_impersonation_token(org.id)

    return AdminImpersonateResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        organization=AdminOrganizationSummary(
            id=org.id,
            name=org.name,
            phone_number=org.phone_number,
            phone_country_code=org.phone_country_code,
            status=str(org.status),
            whatsapp_connected=bool(org.whatsapp_phone_number_id),
            created_at=org.created_at,
        ),
    )


@router.patch(
    "/organizations/{org_id}/status",
    response_model=AdminOrganizationSummary,
    dependencies=[Depends(require_admin)],
)
async def update_organization_status(
    org_id: UUID,
    status_update: AdminOrgStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOrganizationSummary:
    """Suspend or reactivate an organization."""
    if status_update.status not in ["active", "suspended"]:
        raise HTTPException(
            status_code=400, detail="Status must be 'active' or 'suspended'"
        )

    org = await admin_service.update_organization_status(
        db, org_id, status_update.status
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    await db.commit()

    return AdminOrganizationSummary(
        id=org.id,
        name=org.name,
        phone_number=org.phone_number,
        phone_country_code=org.phone_country_code,
        status=str(org.status),
        whatsapp_connected=bool(org.whatsapp_phone_number_id),
        created_at=org.created_at,
    )


@router.delete(
    "/organizations/{org_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
async def delete_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Permanently delete an organization and all associated data.

    This is a destructive operation that cannot be undone. It will delete:
    - The organization
    - All locations and spots
    - All staff and their availability
    - All customers, conversations, and messages
    - All appointments
    - All auth tokens and execution traces
    - Related onboarding sessions
    """
    deleted = await admin_service.delete_organization(db, org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
    return Response(status_code=204)


# Conversations
@router.get(
    "/conversations",
    response_model=list[AdminConversationSummary],
    dependencies=[Depends(require_admin)],
)
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[UUID | None, Query()] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AdminConversationSummary]:
    """List conversations across all organizations."""
    try:
        data = await admin_service.list_conversations(db, org_id, skip, limit)
    except Exception as e:
        logger.exception("Failed to list conversations")
        raise HTTPException(status_code=500, detail=str(e))

    results = []
    for item in data:
        conv = item["conversation"]
        # Skip conversations with missing relationships (orphaned data)
        if not conv.organization or not conv.end_customer:
            logger.warning(
                f"Skipping conversation {conv.id} with missing relationship: "
                f"organization={conv.organization_id}, end_customer={conv.end_customer_id}"
            )
            continue
        results.append(
            AdminConversationSummary(
                id=conv.id,
                organization_id=conv.organization_id,
                organization_name=conv.organization.name,
                customer_phone=conv.end_customer.phone_number,
                customer_name=conv.end_customer.name,
                status=str(conv.status),
                message_count=item["message_count"],
                last_message_at=conv.last_message_at,
                created_at=conv.created_at,
            )
        )
    return results


@router.get(
    "/conversations/{conversation_id}",
    response_model=AdminConversationDetail,
    dependencies=[Depends(require_admin)],
)
async def get_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminConversationDetail:
    """Get conversation with all messages."""
    data = await admin_service.get_conversation_with_messages(db, conversation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = data["conversation"]
    messages = data["messages"]

    # Handle missing relationships (orphaned data)
    if not conv.organization or not conv.end_customer:
        logger.warning(
            f"Conversation {conv.id} has missing relationship: "
            f"organization={conv.organization_id}, end_customer={conv.end_customer_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Conversation has missing organization or customer data",
        )

    return AdminConversationDetail(
        id=conv.id,
        organization_id=conv.organization_id,
        organization_name=conv.organization.name,
        customer_phone=conv.end_customer.phone_number,
        customer_name=conv.end_customer.name,
        status=str(conv.status),
        message_count=len(messages),
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
        messages=[
            AdminMessageDetail(
                id=m.id,
                direction=str(m.direction),
                sender_type=str(m.sender_type),
                content=m.content or "",
                content_type=str(m.content_type),
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


# Activity Feed
@router.get(
    "/activity",
    response_model=list[AdminActivityItem],
    dependencies=[Depends(require_admin)],
)
async def get_activity_feed(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[AdminActivityItem]:
    """Get recent activity feed."""
    activities = await admin_service.get_activity_feed(db, limit)
    return [AdminActivityItem(**a) for a in activities]


# =============================================================================
# Playground Endpoints - Debug conversation UI
# =============================================================================


@router.get(
    "/playground/users",
    response_model=list[PlaygroundUserSummary],
    dependencies=[Depends(require_admin)],
)
async def list_playground_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    limit: int = 100,
) -> list[PlaygroundUserSummary]:
    """List all users (staff and customers) for the playground dropdown."""
    users = await playground_service.list_playground_users(db, search, limit)
    return [PlaygroundUserSummary(**u) for u in users]


@router.get(
    "/playground/users/{phone_number}",
    response_model=PlaygroundUserDetail,
    dependencies=[Depends(require_admin)],
)
async def get_playground_user(
    phone_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaygroundUserDetail:
    """Get detailed user info for the playground info panel."""
    user = await playground_service.get_user_detail(db, phone_number)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return PlaygroundUserDetail(**user)


@router.post(
    "/playground/send",
    response_model=PlaygroundSendResponse,
    dependencies=[Depends(require_admin)],
)
async def send_playground_message(
    request: PlaygroundSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaygroundSendResponse:
    """Send a message through the playground (emulating a user).

    Processes the message through the real AI pipeline but doesn't
    send an actual WhatsApp response. Returns the AI response and
    execution trace exchange_id for debugging.
    """
    result = await playground_service.send_playground_message(
        db, request.phone_number, request.message_content
    )
    return PlaygroundSendResponse(**result)


@router.get(
    "/playground/exchanges",
    response_model=PlaygroundExchangeListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_playground_exchanges(
    db: Annotated[AsyncSession, Depends(get_db)],
    phone_number: Annotated[str | None, Query()] = None,
    org_id: Annotated[UUID | None, Query()] = None,
    limit: int = 20,
) -> PlaygroundExchangeListResponse:
    """List recent message exchanges with their traces."""
    exchanges = await playground_service.list_recent_exchanges(
        db, phone_number, org_id, limit
    )
    return PlaygroundExchangeListResponse(
        phone_number=phone_number or "",
        exchanges=[
            TraceExchangeSummary(
                exchange_id=e["exchange_id"],
                created_at=e["created_at"],
                total_latency_ms=e["total_latency_ms"],
                step_count=e["step_count"],
                user_message_preview=e["user_message_preview"],
                ai_response_preview=e["ai_response_preview"],
                steps=[TraceStepSummary(**s) for s in e["steps"]],
            )
            for e in exchanges
        ],
    )


@router.get(
    "/playground/traces",
    response_model=PlaygroundTraceListResponse,
    dependencies=[Depends(require_admin)],
)
async def get_exchange_traces(
    exchange_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaygroundTraceListResponse:
    """Get all traces for a specific exchange."""
    traces = await playground_service.get_exchange_traces(db, exchange_id)
    if not traces:
        raise HTTPException(status_code=404, detail="Exchange not found")

    total_latency = sum(t["latency_ms"] for t in traces)
    return PlaygroundTraceListResponse(
        exchange_id=exchange_id,
        total_latency_ms=total_latency,
        traces=[TraceStepSummary(**t) for t in traces],
    )


@router.get(
    "/playground/traces/{trace_id}",
    response_model=TraceStepDetail,
    dependencies=[Depends(require_admin)],
)
async def get_trace_detail(
    trace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TraceStepDetail:
    """Get full detail of a single trace step (for L3 modal)."""
    trace = await playground_service.get_trace_detail(db, trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return TraceStepDetail(**trace)


# =============================================================================
# Logs Endpoints - Function trace viewer
# =============================================================================


@router.get(
    "/logs",
    response_model=CorrelationListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    phone_number: Annotated[str | None, Query()] = None,
    organization_id: Annotated[UUID | None, Query()] = None,
    errors_only: Annotated[bool, Query()] = False,
    skip: int = 0,
    limit: int = 50,
) -> CorrelationListResponse:
    """List correlation summaries (grouped function traces).

    Each correlation represents a single request (e.g., a webhook handler invocation).
    All traced functions within that request are grouped under the same correlation_id.
    """
    summaries, total_count = await admin_service.list_correlation_summaries(
        db,
        phone_number=phone_number,
        organization_id=organization_id,
        errors_only=errors_only,
        skip=skip,
        limit=limit,
    )

    return CorrelationListResponse(
        correlations=[CorrelationSummary(**s) for s in summaries],
        total_count=total_count,
        has_more=skip + limit < total_count,
    )


@router.get(
    "/logs/{correlation_id}",
    response_model=CorrelationDetail,
    dependencies=[Depends(require_admin)],
)
async def get_correlation(
    correlation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CorrelationDetail:
    """Get all traces for a specific correlation (request)."""
    data = await admin_service.get_correlation_detail(db, correlation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Correlation not found")

    return CorrelationDetail(
        correlation_id=data["correlation_id"],
        phone_number=data["phone_number"],
        organization_id=data["organization_id"],
        organization_name=data["organization_name"],
        started_at=data["started_at"],
        total_duration_ms=data["total_duration_ms"],
        trace_count=data["trace_count"],
        has_errors=data["has_errors"],
        entry_function=data["entry_function"],
        traces=[TraceItem(**t) for t in data["traces"]],
    )


@router.get(
    "/logs/{correlation_id}/traces/{trace_id}",
    response_model=TraceItem,
    dependencies=[Depends(require_admin)],
)
async def get_log_trace_detail(
    correlation_id: UUID,
    trace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TraceItem:
    """Get a single trace by ID."""
    trace_data = await admin_service.get_trace_detail(db, trace_id)
    if not trace_data:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Verify the trace belongs to the specified correlation
    if trace_data["correlation_id"] != correlation_id:
        raise HTTPException(status_code=404, detail="Trace not found in this correlation")

    return TraceItem(**trace_data)
