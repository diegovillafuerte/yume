"""Schemas for message simulation endpoints."""

from pydantic import BaseModel


class SimulateMessageRequest(BaseModel):
    """Request to simulate an incoming WhatsApp message."""

    sender_phone: str  # "+525512345678"
    recipient_phone: str  # Parlo Central number or business number
    message_body: str
    sender_name: str | None = None


class SimulateMessageResponse(BaseModel):
    """Response from simulating a message."""

    message_id: str
    status: str
    case: str | None = None
    route: str | None = None
    response_text: str | None = None
    sender_type: str | None = None
    organization_id: str | None = None


class SimulationRecipient(BaseModel):
    """A recipient available for simulation."""

    phone_number: str
    label: str  # "Parlo Central" or business name
    type: str  # "central" | "business"
    organization_id: str | None = None
