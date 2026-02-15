"""Handoff relay service — connects customers directly with business owners via WhatsApp.

When a customer explicitly asks to speak to a human, the AI calls handoff_to_human.
This service:
1. Pauses AI for that customer conversation
2. Notifies the owner via WhatsApp
3. Relays messages between customer and owner through the business number
4. Resumes AI when the owner says they're done
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import OpenAIClient, get_openai_client
from app.models import (
    Conversation,
    ConversationStatus,
    EndCustomer,
    Organization,
    ParloUser,
    ParloUserRole,
)
from app.services.tracing import traced
from app.services.whatsapp import WhatsAppClient, resolve_whatsapp_sender

logger = logging.getLogger(__name__)


@traced(capture_args=["reason"])
async def initiate_handoff(
    db: AsyncSession,
    org: Organization,
    customer: EndCustomer,
    conversation: Conversation,
    reason: str,
    mock_mode: bool = False,
) -> dict[str, Any]:
    """Initiate a handoff from AI to business owner.

    Args:
        db: Database session
        org: Organization
        customer: The customer requesting handoff
        conversation: The customer's conversation
        reason: Reason for handoff
        mock_mode: If True, mock WhatsApp messages

    Returns:
        Dict with owner info or error
    """
    # Find first active owner for this org
    owner = await _find_owner(db, org.id)
    if not owner:
        logger.warning(f"No active owner found for org {org.id}")
        return {"error": "no_owner", "message": "No hay personal disponible en este momento."}

    # Check if owner already has an active handoff
    existing = await get_active_handoff_for_owner(db, org.id, owner.id)
    if existing:
        logger.info(f"Owner {owner.name} already has an active handoff")
        return {
            "error": "owner_busy",
            "message": "El equipo está atendiendo a otro cliente en este momento.",
        }

    # Set conversation to handed off
    customer_name = customer.name or customer.phone_number
    conversation.status = ConversationStatus.HANDED_OFF.value
    context = dict(conversation.context or {})
    context.update(
        {
            "handoff_owner_id": str(owner.id),
            "handoff_owner_phone": owner.phone_number,
            "handoff_reason": reason,
            "handoff_started_at": datetime.now(UTC).isoformat(),
            "handoff_customer_phone": customer.phone_number,
            "handoff_customer_name": customer_name,
        }
    )
    conversation.context = context
    await db.flush()

    # Send notification to owner via WhatsApp (from business number)
    whatsapp = WhatsAppClient(mock_mode=mock_mode)
    from_number = resolve_whatsapp_sender(org)

    notification = (
        f"\U0001f514 Un cliente necesita tu ayuda\n"
        f"\n"
        f"Cliente: {customer_name} ({customer.phone_number})\n"
        f"Razón: {reason}\n"
        f"\n"
        f"Responde aquí para hablar directamente con {customer_name}.\n"
        f"Todo lo que escribas se le enviará.\n"
        f'Cuando termines, escribe "listo" o "terminé" y retomo la conversación automáticamente.'
    )

    await whatsapp.send_text_message(
        phone_number_id=from_number or "",
        to=owner.phone_number,
        message=notification,
        from_number=from_number,
    )

    logger.info(
        f"Handoff initiated: customer={customer_name} → owner={owner.name} "
        f"(org={org.name}, reason={reason})"
    )

    return {
        "success": True,
        "handoff_initiated": True,
        "owner_name": owner.name,
        "owner_id": str(owner.id),
    }


@traced(capture_args=[])
async def relay_customer_to_owner(
    db: AsyncSession,
    org: Organization,
    conversation: Conversation,
    message_content: str,
    mock_mode: bool = False,
) -> None:
    """Relay a customer message to the owner during handoff.

    Args:
        db: Database session
        org: Organization
        conversation: The handed-off conversation
        message_content: Customer's message
        mock_mode: If True, mock WhatsApp messages
    """
    context = conversation.context or {}
    owner_phone = context.get("handoff_owner_phone")
    customer_name = context.get("handoff_customer_name", "Cliente")

    if not owner_phone:
        logger.error(f"Handoff conversation {conversation.id} missing owner phone")
        return

    whatsapp = WhatsAppClient(mock_mode=mock_mode)
    from_number = resolve_whatsapp_sender(org)

    await whatsapp.send_text_message(
        phone_number_id=from_number or "",
        to=owner_phone,
        message=f"\U0001f4e9 {customer_name}: {message_content}",
        from_number=from_number,
    )

    # Update last_message_at to prevent timeout
    conversation.last_message_at = datetime.now(UTC)
    await db.flush()


@traced(capture_args=[])
async def relay_owner_to_customer(
    db: AsyncSession,
    org: Organization,
    conversation: Conversation,
    message_content: str,
    mock_mode: bool = False,
) -> None:
    """Relay an owner message to the customer during handoff.

    Args:
        db: Database session
        org: Organization
        conversation: The handed-off conversation
        message_content: Owner's message
        mock_mode: If True, mock WhatsApp messages
    """
    context = conversation.context or {}
    customer_phone = context.get("handoff_customer_phone")
    customer_name = context.get("handoff_customer_name", "Cliente")
    owner_phone = context.get("handoff_owner_phone")

    if not customer_phone or not owner_phone:
        logger.error(f"Handoff conversation {conversation.id} missing phone numbers")
        return

    whatsapp = WhatsAppClient(mock_mode=mock_mode)
    from_number = resolve_whatsapp_sender(org)

    # Send owner's message to customer (from business number)
    await whatsapp.send_text_message(
        phone_number_id=from_number or "",
        to=customer_phone,
        message=message_content,
        from_number=from_number,
    )

    # Send confirmation to owner
    await whatsapp.send_text_message(
        phone_number_id=from_number or "",
        to=owner_phone,
        message=f"\u2709\ufe0f Enviado a {customer_name}",
        from_number=from_number,
    )

    # Update last_message_at to prevent timeout
    conversation.last_message_at = datetime.now(UTC)
    await db.flush()


@traced(capture_args=[])
async def classify_owner_intent(
    message: str,
    customer_name: str,
    client: OpenAIClient | None = None,
) -> str:
    """Classify whether the owner wants to relay a message or end the handoff.

    Uses a lightweight LLM call to determine intent.

    Args:
        message: Owner's message text
        customer_name: Name of the customer being helped
        client: OpenAI client (uses singleton if not provided)

    Returns:
        "relay" or "end"
    """
    client = client or get_openai_client()

    if not client.is_configured:
        return "relay"

    prompt = (
        f"Eres un clasificador. Un dueño de negocio está en conversación con un cliente "
        f"llamado {customer_name}. Determina si el dueño quiere:\n"
        f'- "relay": enviar este mensaje al cliente\n'
        f'- "end": terminar la conversación y devolver al cliente al asistente virtual\n\n'
        f"Responde SOLO con una palabra: relay o end.\n\n"
        f"Ejemplos de end: 'ya terminé', 'listo', 'ya está', 'fin', 'terminar', "
        f"'regresa al bot', 'devuélvelo al AI'\n"
        f"Todo lo demás es relay."
    )

    try:
        response = client.create_message(
            system_prompt=prompt,
            messages=[{"role": "user", "content": message}],
            max_tokens=10,
            model="gpt-4.1-nano",
        )
        result = client.extract_text_response(response).strip().lower()
        if result in ("relay", "end"):
            return result
        # If unclear, default to relay (safe)
        logger.warning(f"Unexpected intent classification: {result}, defaulting to relay")
        return "relay"
    except Exception as e:
        logger.error(f"Intent classification failed: {e}, defaulting to relay")
        return "relay"


@traced(capture_args=[])
async def end_handoff(
    db: AsyncSession,
    org: Organization,
    conversation: Conversation,
    mock_mode: bool = False,
) -> None:
    """End an active handoff, resume AI for the customer.

    Args:
        db: Database session
        org: Organization
        conversation: The handed-off conversation
        mock_mode: If True, mock WhatsApp messages
    """
    context = conversation.context or {}
    customer_phone = context.get("handoff_customer_phone")
    customer_name = context.get("handoff_customer_name", "Cliente")
    owner_phone = context.get("handoff_owner_phone")

    # Restore conversation to active
    conversation.status = ConversationStatus.ACTIVE.value
    # Clear handoff fields from context but keep other context
    for key in list(context.keys()):
        if key.startswith("handoff_"):
            del context[key]
    conversation.context = context
    conversation.last_message_at = datetime.now(UTC)
    await db.flush()

    whatsapp = WhatsAppClient(mock_mode=mock_mode)
    from_number = resolve_whatsapp_sender(org)

    # Notify owner
    if owner_phone:
        await whatsapp.send_text_message(
            phone_number_id=from_number or "",
            to=owner_phone,
            message=f"\u2705 Conversación con {customer_name} finalizada. Parlo retomará la atención.",
            from_number=from_number,
        )

    # Notify customer
    if customer_phone:
        await whatsapp.send_text_message(
            phone_number_id=from_number or "",
            to=customer_phone,
            message=f"\u00a1Gracias por esperar! Soy la asistente virtual de {org.name}. \u00bfPuedo ayudarte con algo más?",
            from_number=from_number,
        )

    logger.info(f"Handoff ended for conversation {conversation.id}")


async def get_active_handoff_for_owner(
    db: AsyncSession,
    org_id: UUID,
    owner_id: UUID,
) -> Conversation | None:
    """Find an active handoff conversation where this owner is the handler.

    Args:
        db: Database session
        org_id: Organization ID
        owner_id: Owner's ParloUser ID

    Returns:
        Handed-off conversation or None
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.organization_id == org_id,
            Conversation.status == ConversationStatus.HANDED_OFF.value,
            Conversation.context["handoff_owner_id"].astext == str(owner_id),
        )
    )
    return result.scalar_one_or_none()


async def check_handoff_timeouts(  # org-scope-ok: system-wide task
    db: AsyncSession,
    timeout_minutes: int = 30,
) -> int:
    """Find and end handed-off conversations that have timed out.

    Args:
        db: Database session
        timeout_minutes: Minutes of inactivity before timeout

    Returns:
        Number of conversations timed out
    """
    threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

    result = await db.execute(
        select(Conversation).where(
            Conversation.status == ConversationStatus.HANDED_OFF.value,
            Conversation.last_message_at < threshold,
        )
    )
    timed_out = result.scalars().all()

    count = 0
    for conv in timed_out:
        context = conv.context or {}
        customer_phone = context.get("handoff_customer_phone")
        customer_name = context.get("handoff_customer_name", "Cliente")
        owner_phone = context.get("handoff_owner_phone")

        # Look up the org for WhatsApp sender resolution
        org_result = await db.execute(
            select(Organization).where(Organization.id == conv.organization_id)
        )
        org = org_result.scalar_one_or_none()

        # Clear handoff state
        conv.status = ConversationStatus.ACTIVE.value
        for key in list(context.keys()):
            if key.startswith("handoff_"):
                del context[key]
        conv.context = context
        conv.last_message_at = datetime.now(UTC)

        # Notify parties if possible
        if org:
            whatsapp = WhatsAppClient(mock_mode=False)
            from_number = resolve_whatsapp_sender(org)

            if owner_phone:
                try:
                    await whatsapp.send_text_message(
                        phone_number_id=from_number or "",
                        to=owner_phone,
                        message=f"\u23f0 La conversación con {customer_name} se cerró por inactividad. Parlo retomará la atención.",
                        from_number=from_number,
                    )
                except Exception as e:
                    logger.error(f"Failed to notify owner on timeout: {e}")

            if customer_phone:
                try:
                    timeout_msg = (
                        f"\u00a1Hola de nuevo! Soy la asistente virtual de {org.name}. \u00bfPuedo ayudarte con algo más?"
                        if org
                        else "\u00a1Hola de nuevo! \u00bfPuedo ayudarte con algo más?"
                    )
                    await whatsapp.send_text_message(
                        phone_number_id=from_number or "",
                        to=customer_phone,
                        message=timeout_msg,
                        from_number=from_number,
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer on timeout: {e}")

        count += 1
        logger.info(f"Handoff timed out for conversation {conv.id}")

    if count > 0:
        await db.flush()

    return count


async def _find_owner(db: AsyncSession, org_id: UUID) -> ParloUser | None:
    """Find the first active owner for an organization.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        Owner ParloUser or None
    """
    result = await db.execute(
        select(ParloUser)
        .where(
            ParloUser.organization_id == org_id,
            ParloUser.role == ParloUserRole.OWNER.value,
            ParloUser.is_active == True,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()
