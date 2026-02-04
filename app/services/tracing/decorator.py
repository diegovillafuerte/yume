"""The @traced decorator for automatic function call tracing.

Usage:
    @traced
    async def my_function(arg1, arg2):
        ...

    @traced(trace_type="ai_tool")
    async def check_availability(date: str):
        ...

    @traced(capture_args=["message"])  # Only capture specific args
    async def handle_message(db, message, context):
        ...
"""

import asyncio
import functools
import time
from typing import Callable, ParamSpec, TypeVar

from app.models.function_trace import FunctionTrace, FunctionTraceType
from app.services.tracing.context import (
    get_correlation_id,
    get_phone_number,
    get_organization_id,
    get_next_sequence_number,
    add_pending_trace,
)
from app.services.tracing.sanitize import build_input_summary, build_output_summary


P = ParamSpec('P')
T = TypeVar('T')


def traced(
    func: Callable[P, T] | None = None,
    *,
    trace_type: str = FunctionTraceType.SERVICE.value,
    capture_args: list[str] | None = None,
) -> Callable[P, T] | Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to automatically trace function calls.

    Can be used with or without arguments:
        @traced
        async def func(): ...

        @traced(trace_type="ai_tool")
        async def func(): ...

    Args:
        func: The function to decorate (when used without parentheses)
        trace_type: Type of trace ("service", "ai_tool", "external_api")
        capture_args: List of argument names to capture (None = all)

    Returns:
        Decorated function that captures traces
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                corr_id = get_correlation_id()

                # No trace context - just run the function
                if corr_id is None:
                    return await fn(*args, **kwargs)

                # Capture input
                input_summary = build_input_summary(fn, args, kwargs, capture_args)

                # Get sequence number
                seq = get_next_sequence_number()

                # Execute and time
                start = time.perf_counter()
                error_info: tuple[str, str] | None = None
                output_summary: dict = {}

                try:
                    result = await fn(*args, **kwargs)
                    output_summary = build_output_summary(result)
                    return result
                except Exception as e:
                    error_info = (type(e).__name__, str(e)[:500])
                    raise
                finally:
                    duration_ms = int((time.perf_counter() - start) * 1000)

                    # Create trace record
                    trace = FunctionTrace(
                        correlation_id=corr_id,
                        sequence_number=seq,
                        function_name=fn.__name__,
                        module_path=fn.__module__,
                        trace_type=trace_type,
                        input_summary=input_summary,
                        output_summary=output_summary,
                        duration_ms=duration_ms,
                        phone_number=get_phone_number(),
                        organization_id=get_organization_id(),
                        is_error=error_info is not None,
                        error_type=error_info[0] if error_info else None,
                        error_message=error_info[1] if error_info else None,
                    )
                    add_pending_trace(trace)

            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                corr_id = get_correlation_id()

                # No trace context - just run the function
                if corr_id is None:
                    return fn(*args, **kwargs)

                # Capture input
                input_summary = build_input_summary(fn, args, kwargs, capture_args)

                # Get sequence number
                seq = get_next_sequence_number()

                # Execute and time
                start = time.perf_counter()
                error_info: tuple[str, str] | None = None
                output_summary: dict = {}

                try:
                    result = fn(*args, **kwargs)
                    output_summary = build_output_summary(result)
                    return result
                except Exception as e:
                    error_info = (type(e).__name__, str(e)[:500])
                    raise
                finally:
                    duration_ms = int((time.perf_counter() - start) * 1000)

                    # Create trace record
                    trace = FunctionTrace(
                        correlation_id=corr_id,
                        sequence_number=seq,
                        function_name=fn.__name__,
                        module_path=fn.__module__,
                        trace_type=trace_type,
                        input_summary=input_summary,
                        output_summary=output_summary,
                        duration_ms=duration_ms,
                        phone_number=get_phone_number(),
                        organization_id=get_organization_id(),
                        is_error=error_info is not None,
                        error_type=error_info[0] if error_info else None,
                        error_message=error_info[1] if error_info else None,
                    )
                    add_pending_trace(trace)

            return sync_wrapper

    # Handle both @traced and @traced() syntax
    if func is not None:
        return decorator(func)
    return decorator
