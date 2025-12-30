"""WhatsApp webhook endpoints - receive messages from Twilio."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.services.message_router import MessageRouter
from app.services.whatsapp import WhatsAppClient

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _extract_phone_number(twilio_number: str) -> str:
    """Extract phone number from Twilio format.

    Args:
        twilio_number: Number in format 'whatsapp:+14155238886'

    Returns:
        Phone number with + prefix (e.g., '+14155238886')
    """
    # Remove 'whatsapp:' prefix if present
    if twilio_number.startswith("whatsapp:"):
        phone = twilio_number[9:]
    else:
        phone = twilio_number

    # Fix URL encoding issue: spaces should be +
    # In form data, + is decoded as space, so convert back
    phone = phone.strip()
    if phone and not phone.startswith("+"):
        phone = f"+{phone}"

    return phone


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_twilio_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    MessageSid: Annotated[str, Form()],
    From: Annotated[str, Form()],
    To: Annotated[str, Form()],
    Body: Annotated[str, Form()],
    ProfileName: Annotated[str | None, Form()] = None,
    NumMedia: Annotated[str | None, Form()] = None,
) -> PlainTextResponse:
    """Receive incoming WhatsApp messages from Twilio.

    Twilio sends webhook data as form-encoded POST.

    Args:
        MessageSid: Unique message identifier
        From: Sender number (format: whatsapp:+14155238886)
        To: Recipient number (our Twilio number)
        Body: Message content
        ProfileName: Sender's WhatsApp profile name
        NumMedia: Number of media attachments

    Returns:
        Empty TwiML response (or with reply message)
    """
    logger.info(
        f"\n{'='*80}\n"
        f"📬 TWILIO WEBHOOK RECEIVED\n"
        f"{'='*80}\n"
        f"  MessageSid: {MessageSid}\n"
        f"  From: {From}\n"
        f"  To: {To}\n"
        f"  Body: {Body}\n"
        f"  ProfileName: {ProfileName}\n"
        f"{'='*80}"
    )

    try:
        # Extract phone numbers
        sender_phone = _extract_phone_number(From)
        our_number = _extract_phone_number(To)

        # Skip media-only messages for now
        if NumMedia and int(NumMedia) > 0 and not Body:
            logger.info(f"Skipping media-only message (no text)")
            return PlainTextResponse(content="", media_type="text/xml")

        # Initialize WhatsApp client
        mock_mode = not settings.twilio_account_sid
        if mock_mode:
            logger.info("🔧 WhatsApp client in MOCK mode (no TWILIO credentials)")
        else:
            logger.info("✅ WhatsApp client in REAL mode")

        whatsapp_client = WhatsAppClient(mock_mode=mock_mode)

        # Initialize message router
        message_router = MessageRouter(db=db, whatsapp_client=whatsapp_client)

        # Route the message
        # Note: phone_number_id is not used by Twilio, pass our number for org lookup
        await message_router.route_message(
            phone_number_id=our_number,
            sender_phone=sender_phone,
            message_id=MessageSid,
            message_content=Body,
            sender_name=ProfileName,
        )

        # Return empty TwiML (we send responses via the API, not TwiML)
        return PlainTextResponse(content="", media_type="text/xml")

    except Exception as e:
        logger.error(f"❌ Error processing Twilio webhook: {e}", exc_info=True)
        # Return empty response to avoid Twilio retries
        return PlainTextResponse(content="", media_type="text/xml")


@router.get("/whatsapp/status", status_code=status.HTTP_200_OK)
async def webhook_status() -> dict[str, str]:
    """Health check endpoint for webhook configuration."""
    return {
        "status": "ok",
        "provider": "twilio",
        "whatsapp_number": settings.twilio_whatsapp_number or "not configured",
    }
