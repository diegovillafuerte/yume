"""Organization API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_org_access
from app.models import Organization
from app.schemas.organization import (
    OrganizationConnectWhatsApp,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services import organization as org_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    org_data: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Create a new organization (onboarding step 1)."""
    org = await org_service.create_organization(db, org_data)
    await db.commit()
    return org


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization by ID",
)
async def get_organization(
    org: Annotated[Organization, Depends(require_org_access)],
) -> Organization:
    """Get organization details by ID."""
    return org


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
)
async def update_organization(
    org_data: OrganizationUpdate,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Update organization details."""
    org = await org_service.update_organization(db, org, org_data)
    await db.commit()
    return org


@router.post(
    "/{org_id}/connect-whatsapp",
    response_model=OrganizationResponse,
    summary="Connect WhatsApp to organization",
)
async def connect_whatsapp(
    whatsapp_data: OrganizationConnectWhatsApp,
    org: Annotated[Organization, Depends(require_org_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Connect WhatsApp via Embedded Signup (onboarding step 2)."""
    if org.whatsapp_phone_number_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp already connected to this organization",
        )

    org = await org_service.connect_whatsapp(db, org, whatsapp_data)
    await db.commit()
    return org
