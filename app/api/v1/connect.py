"""WhatsApp Business connection endpoints for onboarding.

These endpoints handle the Meta Embedded Signup flow where business owners
connect their WhatsApp Business account during onboarding.

Flow:
1. AI sends user a connect URL with token: /connect?token=xxx
2. User opens URL in browser, sees connect page
3. Frontend calls GET /api/v1/connect/session?token=xxx to get session info
4. User clicks "Connect with Facebook" → Meta Embedded Signup
5. Frontend receives credentials from Meta
6. Frontend calls POST /api/v1/connect/complete with credentials
7. Backend creates Organization and marks onboarding complete
8. Frontend shows success and deep-links back to WhatsApp
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models import (
    Location,
    OnboardingSession,
    OnboardingState,
    Organization,
    OrganizationStatus,
    ServiceType,
    Spot,
    Staff,
    StaffRole,
)

router = APIRouter(prefix="/connect", tags=["connect"])
logger = logging.getLogger(__name__)

# Default business hours
DEFAULT_BUSINESS_HOURS = {
    "monday": {"open": "09:00", "close": "19:00"},
    "tuesday": {"open": "09:00", "close": "19:00"},
    "wednesday": {"open": "09:00", "close": "19:00"},
    "thursday": {"open": "09:00", "close": "19:00"},
    "friday": {"open": "09:00", "close": "19:00"},
    "saturday": {"open": "09:00", "close": "17:00"},
    "sunday": {"closed": True},
}


class SessionInfoResponse(BaseModel):
    """Response with onboarding session info for connect page."""

    session_id: str
    business_name: str
    owner_name: str | None
    services: list[dict]
    state: str


class WhatsAppConnectRequest(BaseModel):
    """Request to complete WhatsApp Business connection."""

    token: str
    phone_number_id: str  # Meta's phone number ID
    waba_id: str  # WhatsApp Business Account ID
    access_token: str  # Long-lived access token


class ConnectCompleteResponse(BaseModel):
    """Response after completing connection."""

    success: bool
    organization_id: str
    business_name: str
    dashboard_url: str
    message: str


@router.get("/session", response_model=SessionInfoResponse)
async def get_session_by_token(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionInfoResponse:
    """Get onboarding session info for connection page.

    Args:
        token: Connection token from URL
        db: Database session

    Returns:
        Session info including business name and services
    """
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.connection_token == token,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada o token inválido",
        )

    # Check if session is in valid state for connection
    if session.state == OnboardingState.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta ya fue configurada",
        )

    if session.state == OnboardingState.ABANDONED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta sesión fue abandonada. Por favor inicia de nuevo.",
        )

    collected = session.collected_data or {}

    return SessionInfoResponse(
        session_id=str(session.id),
        business_name=collected.get("business_name", "Sin nombre"),
        owner_name=collected.get("owner_name") or session.owner_name,
        services=collected.get("services", []),
        state=session.state,
    )


@router.post("/complete", response_model=ConnectCompleteResponse)
async def complete_whatsapp_connection(
    data: WhatsAppConnectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectCompleteResponse:
    """Complete WhatsApp Business connection and create organization.

    This is called by the frontend after the user completes Meta Embedded Signup.

    Args:
        data: WhatsApp credentials from Meta
        db: Database session

    Returns:
        Success response with organization info
    """
    # Find session by token
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.connection_token == data.token,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada",
        )

    if session.state == OnboardingState.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta ya fue configurada",
        )

    collected = session.collected_data or {}

    # Validate required data
    if not collected.get("business_name"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del negocio",
        )

    if not collected.get("services"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta al menos un servicio",
        )

    # Store WhatsApp credentials in session
    session.whatsapp_phone_number_id = data.phone_number_id
    session.whatsapp_waba_id = data.waba_id
    session.whatsapp_access_token = data.access_token

    try:
        # Create organization and related entities
        org = await _create_organization_from_session(db, session)

        # Mark session as completed
        session.state = OnboardingState.COMPLETED.value
        session.organization_id = str(org.id)

        await db.commit()

        logger.info(f"Organization created via WhatsApp connect: {org.id} - {org.name}")

        return ConnectCompleteResponse(
            success=True,
            organization_id=str(org.id),
            business_name=org.name,
            dashboard_url="https://yume-production.up.railway.app/login",
            message="¡Tu cuenta está lista!",
        )

    except Exception as e:
        logger.error(f"Error creating organization: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando la cuenta: {str(e)}",
        )


async def _create_organization_from_session(
    db: AsyncSession,
    session: OnboardingSession,
) -> Organization:
    """Create organization and all related entities from onboarding session.

    Args:
        db: Database session
        session: Onboarding session with collected data

    Returns:
        Created organization
    """
    collected = session.collected_data

    # Extract country code
    phone = session.phone_number
    if phone.startswith("+"):
        phone = phone[1:]
    country_code = "52" if phone.startswith("52") else ("1" if phone.startswith("1") else "52")

    # 1. Create Organization with WhatsApp credentials
    org = Organization(
        name=collected["business_name"],
        phone_country_code=country_code,
        phone_number=session.phone_number,
        whatsapp_phone_number_id=session.whatsapp_phone_number_id,
        whatsapp_waba_id=session.whatsapp_waba_id,
        timezone="America/Mexico_City",
        status=OrganizationStatus.ACTIVE.value,
        settings={
            "language": "es",
            "currency": "MXN",
            "business_type": collected.get("business_type", "salon"),
            "whatsapp_access_token": session.whatsapp_access_token,  # Store token in settings
        },
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)

    # 2. Create Location
    location = Location(
        organization_id=org.id,
        name="Principal",
        address=collected.get("address", ""),
        business_hours=collected.get("business_hours", DEFAULT_BUSINESS_HOURS),
        is_primary=True,
    )
    db.add(location)
    await db.flush()
    await db.refresh(location)

    # 3. Create Services
    services = []
    for svc_data in collected.get("services", []):
        price_cents = int(svc_data["price"] * 100)
        service = ServiceType(
            organization_id=org.id,
            name=svc_data["name"],
            duration_minutes=svc_data["duration_minutes"],
            price_cents=price_cents,
            is_active=True,
        )
        db.add(service)
        services.append(service)

    await db.flush()
    for svc in services:
        await db.refresh(svc)

    # 4. Create default Spot
    spot = Spot(
        organization_id=org.id,
        location_id=location.id,
        name="Estación 1",
        is_active=True,
    )
    db.add(spot)
    await db.flush()
    await db.refresh(spot)
    spot.service_types.extend(services)

    # 5. Create Staff (owner)
    owner_name = collected.get("owner_name") or session.owner_name or "Dueño"
    staff = Staff(
        organization_id=org.id,
        location_id=location.id,
        default_spot_id=spot.id,
        name=owner_name,
        phone_number=session.phone_number,
        role=StaffRole.OWNER.value,
        is_active=True,
        permissions={"can_manage_all": True},
    )
    db.add(staff)
    await db.flush()
    await db.refresh(staff)
    staff.service_types.extend(services)

    return org
