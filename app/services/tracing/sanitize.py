"""Input/output sanitization for trace data.

Provides utilities to create safe summaries of function inputs and outputs
for storage in traces, including truncation and sensitive field masking.
"""

import inspect
from typing import Any, Callable
from uuid import UUID
from datetime import datetime, date


# Maximum string length before truncation
MAX_STRING_LENGTH = 200

# Maximum number of items to show in lists/dicts
MAX_COLLECTION_ITEMS = 10

# Fields that should be masked (case-insensitive partial match)
SENSITIVE_FIELDS = {
    'password', 'token', 'secret', 'key', 'auth', 'credential',
    'api_key', 'apikey', 'access_token', 'refresh_token',
}


def is_sensitive_field(name: str) -> bool:
    """Check if a field name suggests sensitive data."""
    name_lower = name.lower()
    return any(sensitive in name_lower for sensitive in SENSITIVE_FIELDS)


def sanitize_value(value: Any, field_name: str = "", depth: int = 0) -> Any:
    """Sanitize a single value for safe storage.

    Args:
        value: The value to sanitize
        field_name: The name of the field (for sensitive detection)
        depth: Current recursion depth (to prevent infinite loops)

    Returns:
        A sanitized, JSON-serializable representation
    """
    # Check for sensitive field
    if field_name and is_sensitive_field(field_name):
        return "[REDACTED]"

    # Prevent deep recursion
    if depth > 3:
        return f"<{type(value).__name__}>"

    # Handle None
    if value is None:
        return None

    # Handle basic types
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value

    # Handle strings with truncation
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            return value[:MAX_STRING_LENGTH] + f"... ({len(value)} chars)"
        return value

    # Handle bytes
    if isinstance(value, bytes):
        return f"<bytes: {len(value)} bytes>"

    # Handle UUIDs
    if isinstance(value, UUID):
        return str(value)

    # Handle datetime
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()

    # Handle lists/tuples
    if isinstance(value, (list, tuple)):
        type_name = type(value).__name__
        if len(value) > MAX_COLLECTION_ITEMS:
            items = [sanitize_value(v, depth=depth + 1) for v in value[:MAX_COLLECTION_ITEMS]]
            return {
                "_type": type_name,
                "_truncated": True,
                "_total": len(value),
                "items": items,
            }
        return [sanitize_value(v, depth=depth + 1) for v in value]

    # Handle dicts
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION_ITEMS:
            result = {}
            for i, (k, v) in enumerate(value.items()):
                if i >= MAX_COLLECTION_ITEMS:
                    result["_truncated"] = True
                    result["_total"] = len(value)
                    break
                result[str(k)] = sanitize_value(v, field_name=str(k), depth=depth + 1)
            return result
        return {
            str(k): sanitize_value(v, field_name=str(k), depth=depth + 1)
            for k, v in value.items()
        }

    # Handle Pydantic models
    if hasattr(value, 'model_dump'):
        try:
            data = value.model_dump()
            return {
                "_type": type(value).__name__,
                **{k: sanitize_value(v, field_name=k, depth=depth + 1)
                   for k, v in list(data.items())[:MAX_COLLECTION_ITEMS]}
            }
        except Exception:
            pass

    # Handle SQLAlchemy models
    if hasattr(value, '__tablename__'):
        result = {"_type": type(value).__name__}
        if hasattr(value, 'id'):
            result["id"] = str(value.id) if value.id else None
        return result

    # Fallback: type name
    return f"<{type(value).__name__}>"


def build_input_summary(
    func: Callable,
    args: tuple,
    kwargs: dict,
    capture_args: list[str] | None = None,
) -> dict:
    """Build a sanitized summary of function inputs.

    Args:
        func: The function being called
        args: Positional arguments
        kwargs: Keyword arguments
        capture_args: If specified, only capture these argument names

    Returns:
        A dict mapping argument names to sanitized values
    """
    result = {}

    # Get function signature to map positional args to names
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
    except (ValueError, TypeError):
        # Can't get signature, use positional names
        params = [f"arg_{i}" for i in range(len(args))]

    # Map positional args
    for i, arg in enumerate(args):
        if i < len(params):
            param_name = params[i]
            # Skip 'self' and 'cls'
            if param_name in ('self', 'cls'):
                continue
            if capture_args is None or param_name in capture_args:
                result[param_name] = sanitize_value(arg, field_name=param_name)
        else:
            name = f"arg_{i}"
            if capture_args is None or name in capture_args:
                result[name] = sanitize_value(arg)

    # Add kwargs
    for key, value in kwargs.items():
        if capture_args is None or key in capture_args:
            result[key] = sanitize_value(value, field_name=key)

    return result


def build_output_summary(result: Any) -> dict:
    """Build a sanitized summary of function output.

    Args:
        result: The function return value

    Returns:
        A dict representing the sanitized output
    """
    if result is None:
        return {"_value": None}

    sanitized = sanitize_value(result)

    # Wrap primitives in a dict
    if isinstance(sanitized, (str, int, float, bool)):
        return {"_value": sanitized}

    if isinstance(sanitized, dict):
        return sanitized

    if isinstance(sanitized, list):
        return {"_items": sanitized}

    return {"_value": sanitized}
