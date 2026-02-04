"""Permission management for Yume staff actions.

This module implements the permission matrix defined in docs/PROJECT_SPEC.md.
It provides functions to check whether a staff member can perform a specific action.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import YumeUser

# Permission Matrix
# Maps action names to list of permission levels that can perform that action
PERMISSION_MATRIX: dict[str, list[str]] = {
    # Schedule viewing
    "view_own_schedule": ["owner", "admin", "staff", "viewer"],
    "view_full_schedule": ["owner", "admin", "staff", "viewer"],

    # Booking actions
    "create_booking": ["owner", "admin", "staff"],
    "book_walk_in": ["owner", "admin", "staff"],
    "cancel_appointment": ["owner", "admin", "staff"],

    # Attendance tracking
    "mark_attendance": ["owner", "admin", "staff"],
    "mark_appointment_status": ["owner", "admin", "staff"],

    # Time management
    "block_own_time": ["owner", "admin", "staff"],
    "block_time": ["owner", "admin", "staff"],

    # Customer management
    "get_customer_history": ["owner", "admin", "staff"],

    # Statistics (owner/admin only)
    "view_stats": ["owner", "admin"],
    "get_business_stats": ["owner", "admin"],

    # Staff management (owner/admin only)
    "add_staff": ["owner", "admin"],
    "remove_staff": ["owner", "admin"],

    # Owner-only actions
    "change_permissions": ["owner"],
    "change_business_hours": ["owner"],
    "change_service_durations": ["owner"],
    "modify_services": ["owner"],
    "change_staff_permissions": ["owner"],
}

# Tool name to permission action mapping
# Maps STAFF_TOOLS names to their required permission actions
TOOL_PERMISSION_MAP: dict[str, str] = {
    "get_my_schedule": "view_own_schedule",
    "get_business_schedule": "view_full_schedule",
    "block_time": "block_time",
    "mark_appointment_status": "mark_appointment_status",
    "book_walk_in": "book_walk_in",
    "get_customer_history": "get_customer_history",
    "cancel_customer_appointment": "cancel_appointment",
    # Future tools
    "add_staff_member": "add_staff",
    "remove_staff_member": "remove_staff",
    "change_staff_permission": "change_permissions",
    "change_business_hours": "change_business_hours",
    "change_service_duration": "change_service_durations",
    "get_business_stats": "get_business_stats",
}


def has_permission(staff: "YumeUser", action: str) -> bool:
    """Check if a staff member has permission to perform an action.

    Args:
        staff: The YumeUser (staff member) to check
        action: The action name (must be a key in PERMISSION_MATRIX)

    Returns:
        True if the staff member can perform the action, False otherwise
    """
    allowed_levels = PERMISSION_MATRIX.get(action, [])
    return staff.permission_level in allowed_levels


def can_use_tool(staff: "YumeUser", tool_name: str) -> bool:
    """Check if a staff member can use a specific tool.

    Args:
        staff: The YumeUser (staff member) to check
        tool_name: The tool name from STAFF_TOOLS

    Returns:
        True if the staff member can use the tool, False otherwise
    """
    # Get the permission action for this tool
    action = TOOL_PERMISSION_MAP.get(tool_name)

    # If tool not in map, allow by default (for backwards compatibility)
    if action is None:
        return True

    return has_permission(staff, action)


def get_permission_denied_message(action: str, staff: "YumeUser") -> str:
    """Get a user-friendly message explaining why permission was denied.

    Args:
        action: The action that was denied
        staff: The staff member who was denied

    Returns:
        Spanish message explaining the denial
    """
    action_descriptions: dict[str, str] = {
        "view_stats": "ver estadísticas del negocio",
        "get_business_stats": "ver estadísticas del negocio",
        "add_staff": "agregar empleados",
        "remove_staff": "remover empleados",
        "change_permissions": "cambiar permisos de empleados",
        "change_business_hours": "cambiar horarios del negocio",
        "change_service_durations": "cambiar duración de servicios",
        "modify_services": "modificar servicios",
        "view_full_schedule": "ver la agenda completa del negocio",
    }

    action_desc = action_descriptions.get(action, action)

    level_messages = {
        "owner": "Solo el dueño puede",
        "admin": "Solo administradores pueden",
        "staff": "Solo empleados activos pueden",
        "viewer": "No tienes permiso para",
    }

    # Get the minimum required level for this action
    allowed_levels = PERMISSION_MATRIX.get(action, [])
    if "owner" in allowed_levels and len(allowed_levels) == 1:
        prefix = "Solo el dueño puede"
    elif "admin" in allowed_levels and "owner" in allowed_levels and len(allowed_levels) == 2:
        prefix = "Solo el dueño y administradores pueden"
    else:
        prefix = "No tienes permiso para"

    return f"{prefix} {action_desc}."


def get_allowed_tools_for_permission_level(permission_level: str) -> list[str]:
    """Get list of tools a permission level can use.

    Args:
        permission_level: The permission level (owner, admin, staff, viewer)

    Returns:
        List of tool names the permission level can use
    """
    allowed_tools = []

    for tool_name, action in TOOL_PERMISSION_MAP.items():
        allowed_levels = PERMISSION_MATRIX.get(action, [])
        if permission_level in allowed_levels:
            allowed_tools.append(tool_name)

    return allowed_tools


def filter_tools_by_permission(
    tools: list[dict],
    staff: "YumeUser"
) -> list[dict]:
    """Filter a list of tool definitions to only include allowed tools.

    This is useful for providing the AI with only the tools the staff
    member is allowed to use, preventing attempts to use unauthorized tools.

    Args:
        tools: List of tool definitions (from STAFF_TOOLS)
        staff: The staff member

    Returns:
        Filtered list containing only tools the staff can use
    """
    filtered = []

    for tool in tools:
        tool_name = tool.get("name", "")
        if can_use_tool(staff, tool_name):
            filtered.append(tool)

    return filtered
