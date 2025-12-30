"""Authentication API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.schemas.auth import (
    LogoutResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    MagicLinkVerify,
    TokenResponse,
)
from app.services import auth as auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/request-magic-link",
    response_model=MagicLinkResponse,
    summary="Request a magic link",
)
async def request_magic_link(
    request: MagicLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MagicLinkResponse:
    """Request a magic link to be sent via WhatsApp.

    The magic link will be sent to the organization's WhatsApp number.
    """
    settings = get_settings()

    # Find organization by phone number
    organization = await auth_service.get_organization_by_phone(db, request.phone_number)

    if organization is None:
        # Don't reveal if the phone number exists or not
        logger.warning(f"Magic link requested for unknown phone: {request.phone_number}")
        # Still return success to prevent phone enumeration
        return MagicLinkResponse()

    # Create magic link token
    plain_token, auth_token = await auth_service.create_magic_link_token(db, organization.id)
    await db.commit()

    # Build magic link URL
    magic_link_url = f"{settings.frontend_url}/verify?token={plain_token}"

    # In production, send via WhatsApp
    # For now, log it (in development mode)
    if settings.is_development:
        logger.info(f"Magic link for {organization.name}: {magic_link_url}")
        print(f"\n{'='*60}")
        print(f"MAGIC LINK for {organization.name}:")
        print(f"{magic_link_url}")
        print(f"{'='*60}\n")
    else:
        # TODO: Send via WhatsApp API
        # await whatsapp_service.send_magic_link(organization, magic_link_url)
        logger.info(f"Magic link created for organization {organization.id}")

    return MagicLinkResponse()


@router.post(
    "/verify-magic-link",
    response_model=TokenResponse,
    summary="Verify a magic link token",
)
async def verify_magic_link(
    request: MagicLinkVerify,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Verify a magic link token and return an access token.

    The token from the magic link URL is exchanged for a JWT access token.
    """
    settings = get_settings()

    organization, result = await auth_service.verify_magic_link_token(db, request.token)

    if organization is None:
        # result contains the error message
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result or "Invalid or expired token",
        )

    await db.commit()

    # result contains the access_token
    access_token = result

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        organization=organization,  # Will be serialized via OrganizationResponse
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout (invalidate tokens)",
)
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    # TODO: Add auth dependency to get current organization
    # org: Annotated[Organization, Depends(get_current_organization)],
) -> LogoutResponse:
    """Logout by invalidating all pending magic link tokens.

    Note: JWT tokens cannot be invalidated (stateless). They will expire naturally.
    For immediate logout, the client should delete the stored token.
    """
    # TODO: Get organization from auth and invalidate tokens
    # await auth_service.invalidate_organization_tokens(db, org.id)
    # await db.commit()

    return LogoutResponse()
