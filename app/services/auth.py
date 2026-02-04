"""Auth service - business logic for authentication."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AuthToken, Organization, YumeUser
from app.utils.jwt import create_access_token


def generate_magic_link_token() -> tuple[str, str]:
    """Generate a secure magic link token.

    Returns (plain_token, hashed_token).
    The plain token is sent to the user, the hash is stored in the database.
    """
    plain_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()
    return plain_token, hashed_token


async def get_organization_by_phone(
    db: AsyncSession, phone_number: str
) -> Organization | None:
    """Get organization by phone number.

    Checks both the org's phone_number and owner staff phone numbers.
    """
    # First try to match organization phone
    result = await db.execute(
        select(Organization).where(Organization.phone_number == phone_number)
    )
    org = result.scalar_one_or_none()
    if org:
        return org

    # Try matching with country code prefix
    if not phone_number.startswith("+"):
        # Try with +52 (Mexico)
        result = await db.execute(
            select(Organization).where(
                Organization.phone_country_code + Organization.phone_number == "+" + phone_number
            )
        )
        org = result.scalar_one_or_none()
        if org:
            return org

    # Search staff with owner role by phone number
    result = await db.execute(
        select(YumeUser).where(
            YumeUser.phone_number == phone_number,
            YumeUser.role == "owner",
            YumeUser.is_active == True,
        )
    )
    staff = result.scalar_one_or_none()
    if staff:
        # Get the organization for this staff
        org_result = await db.execute(
            select(Organization).where(Organization.id == staff.organization_id)
        )
        return org_result.scalar_one_or_none()

    return None


async def create_magic_link_token(
    db: AsyncSession, organization_id: UUID
) -> tuple[str, AuthToken]:
    """Create a magic link token for an organization.

    Returns (plain_token, auth_token_model).
    The plain token should be included in the magic link URL.
    """
    settings = get_settings()

    plain_token, hashed_token = generate_magic_link_token()

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.magic_link_expire_minutes
    )

    auth_token = AuthToken(
        organization_id=organization_id,
        token_hash=hashed_token,
        token_type="magic_link",
        expires_at=expires_at,
    )
    db.add(auth_token)
    await db.flush()
    await db.refresh(auth_token)

    return plain_token, auth_token


async def verify_magic_link_token(
    db: AsyncSession, plain_token: str
) -> tuple[Organization | None, str | None]:
    """Verify a magic link token and return the organization.

    Returns (organization, access_token) if valid.
    Returns (None, error_message) if invalid.
    """
    hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

    result = await db.execute(
        select(AuthToken).where(AuthToken.token_hash == hashed_token)
    )
    auth_token = result.scalar_one_or_none()

    if auth_token is None:
        return None, "Invalid token"

    if auth_token.used_at is not None:
        return None, "Token already used"

    now = datetime.now(timezone.utc)
    if auth_token.expires_at <= now:
        return None, "Token expired"

    # Mark token as used
    auth_token.used_at = now
    await db.flush()

    # Get the organization
    result = await db.execute(
        select(Organization).where(Organization.id == auth_token.organization_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        return None, "Organization not found"

    # Check if organization is suspended
    if str(organization.status) == "suspended":
        return None, "Organization is suspended"

    # Create access token
    access_token = create_access_token(organization.id)

    return organization, access_token


async def invalidate_organization_tokens(
    db: AsyncSession, organization_id: UUID
) -> None:
    """Invalidate all unused tokens for an organization (logout)."""
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.organization_id == organization_id,
            AuthToken.used_at.is_(None),
        )
    )
    tokens = result.scalars().all()

    now = datetime.now(timezone.utc)
    for token in tokens:
        token.used_at = now

    await db.flush()
