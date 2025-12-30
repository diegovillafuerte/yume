"""Admin API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services import admin as admin_service
from app.utils.jwt import create_admin_access_token

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
    data = await admin_service.list_conversations(db, org_id, skip, limit)
    return [
        AdminConversationSummary(
            id=item["conversation"].id,
            organization_id=item["conversation"].organization_id,
            organization_name=item["conversation"].organization.name,
            customer_phone=item["conversation"].customer.phone_number,
            customer_name=item["conversation"].customer.name,
            status=str(item["conversation"].status),
            message_count=item["message_count"],
            last_message_at=item["conversation"].last_message_at,
            created_at=item["conversation"].created_at,
        )
        for item in data
    ]


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

    return AdminConversationDetail(
        id=conv.id,
        organization_id=conv.organization_id,
        organization_name=conv.organization.name,
        customer_phone=conv.customer.phone_number,
        customer_name=conv.customer.name,
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
