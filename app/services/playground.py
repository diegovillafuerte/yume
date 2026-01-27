"""Playground service - handles admin debug playground operations.

This service provides the business logic for the admin playground UI,
allowing admins to emulate conversations and view execution traces.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Appointment,
    Customer,
    ExecutionTrace,
    Organization,
    Staff,
)
from app.services.execution_tracer import ExecutionTracer
from app.services.message_router import MessageRouter
from app.services.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)


async def list_playground_users(
    db: AsyncSession,
    search: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List all users (staff and customers) for the playground dropdown.

    Args:
        db: Database session
        search: Optional search term for phone number or name
        limit: Maximum number of results

    Returns:
        List of user dicts with type, phone, name, org info
    """
    users = []

    # Get staff members
    staff_query = (
        select(Staff, Organization)
        .join(Organization, Staff.organization_id == Organization.id)
        .where(Staff.is_active == True)
    )

    if search:
        staff_query = staff_query.where(
            (Staff.phone_number.ilike(f"%{search}%"))
            | (Staff.name.ilike(f"%{search}%"))
        )

    staff_query = staff_query.limit(limit // 2)
    staff_result = await db.execute(staff_query)

    for staff, org in staff_result.all():
        users.append({
            "phone_number": staff.phone_number,
            "name": staff.name,
            "user_type": "staff",
            "organization_id": org.id,
            "organization_name": org.name,
            "role": staff.role,
            "user_id": staff.id,
            "is_active": staff.is_active,
            "created_at": staff.created_at,
        })

    # Get customers
    customer_query = (
        select(Customer, Organization)
        .join(Organization, Customer.organization_id == Organization.id)
    )

    if search:
        customer_query = customer_query.where(
            (Customer.phone_number.ilike(f"%{search}%"))
            | (Customer.name.ilike(f"%{search}%"))
        )

    customer_query = customer_query.limit(limit // 2)
    customer_result = await db.execute(customer_query)

    for customer, org in customer_result.all():
        users.append({
            "phone_number": customer.phone_number,
            "name": customer.name,
            "user_type": "customer",
            "organization_id": org.id,
            "organization_name": org.name,
            "role": None,
            "user_id": customer.id,
            "is_active": None,
            "created_at": customer.created_at,
        })

    # Sort by name/phone
    users.sort(key=lambda u: u.get("name") or u.get("phone_number") or "")

    return users[:limit]


async def get_user_detail(
    db: AsyncSession,
    phone_number: str,
) -> dict[str, Any] | None:
    """Get detailed user info for the info panel.

    Args:
        db: Database session
        phone_number: Phone number to look up

    Returns:
        User detail dict or None if not found
    """
    # Check if staff
    staff_result = await db.execute(
        select(Staff, Organization)
        .join(Organization, Staff.organization_id == Organization.id)
        .where(Staff.phone_number == phone_number)
    )
    staff_row = staff_result.first()

    if staff_row:
        staff, org = staff_row
        return {
            "phone_number": staff.phone_number,
            "name": staff.name,
            "user_type": "staff",
            "organization_id": org.id,
            "organization_name": org.name,
            "role": staff.role,
            "user_id": staff.id,
            "is_active": staff.is_active,
            "created_at": staff.created_at,
            "appointment_count": None,
        }

    # Check if customer
    customer_result = await db.execute(
        select(Customer, Organization)
        .join(Organization, Customer.organization_id == Organization.id)
        .where(Customer.phone_number == phone_number)
    )
    customer_row = customer_result.first()

    if customer_row:
        customer, org = customer_row

        # Get appointment count
        apt_count_result = await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.customer_id == customer.id
            )
        )
        appointment_count = apt_count_result.scalar() or 0

        return {
            "phone_number": customer.phone_number,
            "name": customer.name,
            "user_type": "customer",
            "organization_id": org.id,
            "organization_name": org.name,
            "role": None,
            "user_id": customer.id,
            "is_active": None,
            "created_at": customer.created_at,
            "appointment_count": appointment_count,
        }

    return None


async def send_playground_message(
    db: AsyncSession,
    phone_number: str,
    message_content: str,
) -> dict[str, Any]:
    """Send a message through the playground (emulating the user).

    This processes the message through the real pipeline but:
    1. Creates an ExecutionTracer to capture all steps
    2. Skips sending the actual WhatsApp response
    3. Returns the response text and trace exchange_id

    Args:
        db: Database session
        phone_number: Phone number to emulate sending from
        message_content: Message text to send

    Returns:
        Dict with response_text, exchange_id, latency_ms, route
    """
    # First, find the organization for this user to create the tracer
    user_detail = await get_user_detail(db, phone_number)

    if not user_detail:
        # Unknown user - will go through onboarding
        # Create a temporary org ID for tracing (won't be saved)
        # Actually, for onboarding we should just skip tracing for now
        # or use a special "system" org ID
        return {
            "response_text": "Usuario no encontrado en el sistema.",
            "exchange_id": uuid.uuid4(),
            "latency_ms": 0,
            "route": "error",
            "organization_id": None,
        }

    organization_id = user_detail["organization_id"]

    # Create tracer
    tracer = ExecutionTracer(db, organization_id)

    # Create a mock WhatsApp client (won't send real messages)
    whatsapp_client = WhatsAppClient()

    # Create message router
    router = MessageRouter(db, whatsapp_client)

    # Generate a unique message ID for this playground message
    playground_message_id = f"playground_{uuid.uuid4()}"

    # Process the message with tracing and skip_whatsapp_send
    result = await router.route_message(
        phone_number_id="playground",  # Dummy phone number ID
        sender_phone=phone_number,
        message_id=playground_message_id,
        message_content=message_content,
        sender_name=user_detail.get("name"),
        tracer=tracer,
        skip_whatsapp_send=True,
    )

    # Save traces
    await tracer.save_traces()

    return {
        "response_text": result.get("response_text", ""),
        "exchange_id": tracer.get_exchange_id(),
        "latency_ms": tracer.get_total_latency_ms(),
        "route": result.get("route", "unknown"),
        "organization_id": organization_id,
    }


async def get_exchange_traces(
    db: AsyncSession,
    exchange_id: UUID,
) -> list[dict[str, Any]]:
    """Get all traces for an exchange.

    Args:
        db: Database session
        exchange_id: Exchange ID to fetch traces for

    Returns:
        List of trace dicts
    """
    result = await db.execute(
        select(ExecutionTrace)
        .where(ExecutionTrace.exchange_id == exchange_id)
        .order_by(ExecutionTrace.sequence_number)
    )
    traces = result.scalars().all()

    return [
        {
            "id": t.id,
            "exchange_id": t.exchange_id,
            "trace_type": t.trace_type,
            "sequence_number": t.sequence_number,
            "started_at": t.started_at,
            "completed_at": t.completed_at,
            "latency_ms": t.latency_ms,
            "input_data": t.input_data,
            "output_data": t.output_data,
            "metadata": t.metadata,
            "is_error": t.is_error,
            "error_message": t.error_message,
            # Extract useful preview fields
            "tool_name": t.input_data.get("tool_name") if t.trace_type == "tool_execution" else None,
            "llm_call_number": t.input_data.get("llm_call_number") if t.trace_type == "llm_call" else None,
        }
        for t in traces
    ]


async def get_trace_detail(
    db: AsyncSession,
    trace_id: UUID,
) -> dict[str, Any] | None:
    """Get full detail of a single trace.

    Args:
        db: Database session
        trace_id: Trace ID to fetch

    Returns:
        Trace detail dict or None
    """
    trace = await db.get(ExecutionTrace, trace_id)
    if not trace:
        return None

    return {
        "id": trace.id,
        "exchange_id": trace.exchange_id,
        "trace_type": trace.trace_type,
        "sequence_number": trace.sequence_number,
        "started_at": trace.started_at,
        "completed_at": trace.completed_at,
        "latency_ms": trace.latency_ms,
        "input_data": trace.input_data,
        "output_data": trace.output_data,
        "metadata": trace.metadata,
        "is_error": trace.is_error,
        "error_message": trace.error_message,
    }


async def list_recent_exchanges(
    db: AsyncSession,
    phone_number: str | None = None,
    organization_id: UUID | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List recent exchanges, optionally filtered by phone or org.

    Args:
        db: Database session
        phone_number: Optional phone number to filter by
        organization_id: Optional organization ID to filter by
        limit: Maximum number of exchanges to return

    Returns:
        List of exchange summaries
    """
    # Get distinct exchange_ids with their first trace
    # We need to aggregate traces into exchanges

    # First, get distinct exchange_ids ordered by most recent
    query = select(
        ExecutionTrace.exchange_id,
        func.min(ExecutionTrace.created_at).label("created_at"),
        func.sum(ExecutionTrace.latency_ms).label("total_latency_ms"),
        func.count(ExecutionTrace.id).label("step_count"),
    ).group_by(ExecutionTrace.exchange_id)

    if organization_id:
        query = query.where(ExecutionTrace.organization_id == organization_id)

    query = query.order_by(func.min(ExecutionTrace.created_at).desc()).limit(limit)

    result = await db.execute(query)
    exchange_summaries = result.all()

    exchanges = []
    for row in exchange_summaries:
        exchange_id = row.exchange_id

        # Get the traces for this exchange
        traces_result = await db.execute(
            select(ExecutionTrace)
            .where(ExecutionTrace.exchange_id == exchange_id)
            .order_by(ExecutionTrace.sequence_number)
        )
        traces = traces_result.scalars().all()

        # Extract message preview from MESSAGE_RECEIVED trace
        user_message_preview = None
        ai_response_preview = None
        for t in traces:
            if t.trace_type == "message_received":
                user_message_preview = t.input_data.get("message_preview", "")[:100]
            if t.trace_type == "response_assembled":
                ai_response_preview = t.output_data.get("response_preview", "")[:100]

        # Build step summaries
        steps = []
        for t in traces:
            steps.append({
                "id": t.id,
                "trace_type": t.trace_type,
                "sequence_number": t.sequence_number,
                "latency_ms": t.latency_ms,
                "is_error": t.is_error,
                "tool_name": t.input_data.get("tool_name") if t.trace_type == "tool_execution" else None,
                "llm_call_number": t.input_data.get("llm_call_number") if t.trace_type == "llm_call" else None,
            })

        exchanges.append({
            "exchange_id": exchange_id,
            "created_at": row.created_at,
            "total_latency_ms": row.total_latency_ms or 0,
            "step_count": row.step_count or 0,
            "user_message_preview": user_message_preview,
            "ai_response_preview": ai_response_preview,
            "steps": steps,
        })

    return exchanges
