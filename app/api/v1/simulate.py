"""Simulation endpoints for testing message flows without real WhatsApp.

Admin-only. Only registered when APP_ENV != production.
"""

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import require_admin
from app.api.deps import get_db
from app.config import get_settings
from app.models import Organization, OrganizationStatus
from app.schemas.simulate import (
    SimulateMessageRequest,
    SimulateMessageResponse,
    SimulationRecipient,
)
from app.services.message_router import MessageRouter
from app.services.tracing import (
    clear_trace_context,
    save_pending_traces,
    start_trace_context,
)
from app.services.whatsapp import WhatsAppClient

router = APIRouter(
    prefix="/simulate",
    tags=["simulate"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)


@router.post("/message", response_model=SimulateMessageResponse)
async def simulate_message(
    request: SimulateMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimulateMessageResponse:
    """Simulate an incoming WhatsApp message.

    Calls the same MessageRouter.route_message() as the real webhook,
    but with WhatsApp in mock mode so no real messages are sent.
    """
    message_id = f"sim_{uuid4().hex[:16]}"
    correlation_id = start_trace_context(phone_number=request.sender_phone)

    try:
        whatsapp_client = WhatsAppClient(mock_mode=True)
        message_router = MessageRouter(db=db, whatsapp_client=whatsapp_client)

        result = await message_router.route_message(
            phone_number_id=request.recipient_phone,
            sender_phone=request.sender_phone,
            message_id=message_id,
            message_content=request.message_body,
            sender_name=request.sender_name,
        )

        await save_pending_traces(db)
        await db.commit()

        return SimulateMessageResponse(
            message_id=message_id,
            status=result.get("status", "unknown"),
            case=result.get("case"),
            route=result.get("route"),
            response_text=result.get("response_text"),
            sender_type=result.get("sender_type"),
            organization_id=result.get("organization_id"),
        )

    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        try:
            await save_pending_traces(db)
            await db.commit()
        except Exception:
            pass
        raise

    finally:
        clear_trace_context()


@router.get("/recipients", response_model=list[SimulationRecipient])
async def list_simulation_recipients(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SimulationRecipient]:
    """List available recipient numbers for simulation.

    Returns Parlo Central number + all active orgs with a WhatsApp number.
    """
    settings = get_settings()
    recipients: list[SimulationRecipient] = []

    # Parlo Central number
    central_number = settings.twilio_whatsapp_number.replace("whatsapp:", "")
    if central_number:
        recipients.append(
            SimulationRecipient(
                phone_number=central_number,
                label="Parlo Central",
                type="central",
            )
        )

    # Active orgs with WhatsApp numbers
    result = await db.execute(
        select(Organization).where(
            Organization.status == OrganizationStatus.ACTIVE.value,
            Organization.whatsapp_phone_number_id.isnot(None),
            Organization.whatsapp_phone_number_id != "",
        )
    )
    orgs = result.scalars().all()

    for org in orgs:
        recipients.append(
            SimulationRecipient(
                phone_number=org.whatsapp_phone_number_id,
                label=org.name or f"Org {org.id}",
                type="business",
                organization_id=str(org.id),
            )
        )

    return recipients
