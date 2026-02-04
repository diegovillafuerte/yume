"""Tracing infrastructure for automatic function call capture.

This package provides decorator-based tracing that automatically captures
function calls, their inputs, outputs, timing, and errors.

Usage:
    from app.services.tracing import traced, start_trace_context, save_pending_traces

    # At request entry (e.g., webhook handler):
    correlation_id = start_trace_context(phone_number="+52...", organization_id=org.id)

    # Decorate functions to trace:
    @traced
    async def my_function(arg1, arg2):
        ...

    # At request end:
    await save_pending_traces(db)
"""

from app.services.tracing.context import (
    start_trace_context,
    get_correlation_id,
    get_phone_number,
    get_organization_id,
    set_organization_id,
    save_pending_traces,
    clear_trace_context,
)
from app.services.tracing.decorator import traced

__all__ = [
    "traced",
    "start_trace_context",
    "get_correlation_id",
    "get_phone_number",
    "get_organization_id",
    "set_organization_id",
    "save_pending_traces",
    "clear_trace_context",
]
