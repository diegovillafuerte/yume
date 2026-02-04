"""Admin Logs schemas for function trace viewing."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TraceItem(BaseModel):
    """Single trace item within a correlation."""

    id: UUID
    sequence_number: int
    function_name: str
    module_path: str
    trace_type: str  # "service", "ai_tool", "external_api"
    duration_ms: int
    is_error: bool
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CorrelationSummary(BaseModel):
    """Summary of a correlation (grouped traces from one request)."""

    correlation_id: UUID
    phone_number: str | None
    organization_id: UUID | None
    organization_name: str | None
    started_at: datetime
    total_duration_ms: int
    trace_count: int
    has_errors: bool
    entry_function: str  # First function name in the trace


class CorrelationDetail(CorrelationSummary):
    """Full correlation with all traces."""

    traces: list[TraceItem]


class CorrelationListResponse(BaseModel):
    """Response for listing correlations."""

    correlations: list[CorrelationSummary]
    total_count: int
    has_more: bool
