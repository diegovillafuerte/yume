"""Dependency injection for API endpoints."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Organization
from app.services import organization as org_service
from app.utils.jwt import get_organization_id_from_token

__all__ = [
    "get_db",
    "AsyncSession",
    "get_organization_dependency",
    "get_current_organization",
    "require_org_access",
    "PaginationParams",
]

# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# Database session dependency
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session - alias for get_db."""
    async for session in get_db():
        yield session


# Organization lookup dependency
async def get_organization_dependency(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Get organization by ID or raise 404."""
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )
    return org


async def require_org_access(
    org_id: UUID,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Require valid JWT and ensure it matches the requested org_id."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_org_id = get_organization_id_from_token(credentials.credentials)
    if token_org_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this organization",
        )

    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    return org


# Auth dependency - get current organization from JWT
async def get_current_organization(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    """Get the current organization from the JWT token.

    Raises 401 if not authenticated or token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    org_id = get_organization_id_from_token(credentials.credentials)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return org


# Optional auth - doesn't raise if not authenticated
async def get_current_organization_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization | None:
    """Get the current organization from the JWT token, or None if not authenticated."""
    if credentials is None:
        return None

    org_id = get_organization_id_from_token(credentials.credentials)
    if org_id is None:
        return None

    return await org_service.get_organization(db, org_id)


# Pagination parameters
class PaginationParams:
    """Pagination query parameters."""

    def __init__(
        self,
        skip: Annotated[int, Query(ge=0, description="Number of records to skip")] = 0,
        limit: Annotated[
            int, Query(ge=1, le=100, description="Maximum number of records to return")
        ] = 50,
    ):
        self.skip = skip
        self.limit = limit
