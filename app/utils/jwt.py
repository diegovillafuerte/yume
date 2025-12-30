"""JWT utilities for authentication."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pydantic import BaseModel

from app.config import get_settings


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # Subject - organization_id
    exp: datetime  # Expiration time
    iat: datetime  # Issued at
    type: str = "access"  # Token type


def create_access_token(organization_id: UUID) -> str:
    """Create a JWT access token for an organization."""
    settings = get_settings()

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(organization_id),
        "exp": expires,
        "iat": now,
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def decode_access_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT access token.

    Returns TokenPayload if valid, None if invalid or expired.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            type=payload.get("type", "access"),
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_organization_id_from_token(token: str) -> UUID | None:
    """Extract organization ID from a JWT token.

    Returns UUID if valid, None if invalid or expired.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    try:
        return UUID(payload.sub)
    except ValueError:
        return None


def create_admin_access_token() -> str:
    """Create a JWT access token for admin."""
    settings = get_settings()

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": "admin",
        "exp": expires,
        "iat": now,
        "type": "admin_access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def is_admin_token(payload: TokenPayload) -> bool:
    """Check if a token payload is an admin token."""
    return payload.type == "admin_access" and payload.sub == "admin"
