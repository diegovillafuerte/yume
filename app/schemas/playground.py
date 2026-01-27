"""Playground-specific Pydantic schemas for admin debug UI."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# User listing schemas
class PlaygroundUserSummary(BaseModel):
    """Summary of a user (staff or customer) for the playground dropdown."""

    phone_number: str
    name: str | None
    user_type: str = Field(..., description="'staff' or 'customer'")
    organization_id: UUID
    organization_name: str
    # Additional context
    role: str | None = None  # For staff
    user_id: UUID


class PlaygroundUserDetail(PlaygroundUserSummary):
    """Detailed user info for the info panel."""

    created_at: datetime
    # Staff-specific
    is_active: bool | None = None
    # Customer-specific
    appointment_count: int | None = None


# Message sending schemas
class PlaygroundSendRequest(BaseModel):
    """Request to send a message through the playground."""

    phone_number: str = Field(..., description="Phone number to emulate sending from")
    message_content: str = Field(..., description="Message text to send")


class PlaygroundSendResponse(BaseModel):
    """Response after sending a playground message."""

    response_text: str
    exchange_id: UUID
    latency_ms: int
    route: str  # staff, customer, onboarding
    organization_id: UUID | None = None


# Trace schemas
class TraceStepSummary(BaseModel):
    """Summary of a single trace step (for L2 view)."""

    id: UUID
    trace_type: str
    sequence_number: int
    latency_ms: int
    is_error: bool
    # Preview data
    tool_name: str | None = None  # For tool executions
    llm_call_number: int | None = None  # For LLM calls


class TraceExchangeSummary(BaseModel):
    """Summary of a complete message exchange (for L1 view)."""

    exchange_id: UUID
    created_at: datetime
    total_latency_ms: int
    step_count: int
    # Message preview
    user_message_preview: str | None = None
    ai_response_preview: str | None = None
    # Steps for L2 expansion
    steps: list[TraceStepSummary]


class TraceStepDetail(BaseModel):
    """Full detail of a single trace step (for L3 modal)."""

    id: UUID
    exchange_id: UUID
    trace_type: str
    sequence_number: int
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    input_data: dict
    output_data: dict
    metadata: dict
    is_error: bool
    error_message: str | None


class PlaygroundExchangeListResponse(BaseModel):
    """Response containing recent exchanges for a phone number."""

    phone_number: str
    exchanges: list[TraceExchangeSummary]


class PlaygroundTraceListResponse(BaseModel):
    """Response containing all traces for an exchange."""

    exchange_id: UUID
    total_latency_ms: int
    traces: list[TraceStepSummary]
