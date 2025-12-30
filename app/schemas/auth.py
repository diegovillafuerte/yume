"""Pydantic schemas for Authentication."""

from pydantic import BaseModel, Field

from app.schemas.organization import OrganizationResponse


class MagicLinkRequest(BaseModel):
    """Request to send a magic link."""

    phone_number: str = Field(
        ...,
        description="Phone number to send the magic link to (organization's WhatsApp)",
    )


class MagicLinkResponse(BaseModel):
    """Response after sending a magic link."""

    message: str = Field(
        default="Magic link sent via WhatsApp",
        description="Success message",
    )


class MagicLinkVerify(BaseModel):
    """Request to verify a magic link token."""

    token: str = Field(..., description="The magic link token from the URL")


class TokenResponse(BaseModel):
    """Response after successful authentication."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    organization: OrganizationResponse


class LogoutResponse(BaseModel):
    """Response after logout."""

    message: str = Field(default="Logged out successfully")
