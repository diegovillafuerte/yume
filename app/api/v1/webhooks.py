"""WhatsApp webhook endpoints - receive messages from Twilio."""

import logging
import base64
import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.models import Organization
from app.services.message_router import MessageRouter
from app.services.whatsapp import WhatsAppClient
from app.services.tracing import start_trace_context, set_organization_id, save_pending_traces, clear_trace_context

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


def _verify_twilio_signature(
    request_url: str, params: dict[str, str], signature: str, auth_token: str
) -> bool:
    """Verify Twilio webhook signature."""
    data = request_url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


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

    # Verify Twilio signature (if enabled)
    validate_signature = settings.twilio_validate_signature
    if settings.is_development and not settings.twilio_auth_token:
        validate_signature = False

    if validate_signature:
        signature = request.headers.get("X-Twilio-Signature", "")
        if not settings.twilio_auth_token:
            logger.error("Twilio signature validation enabled but TWILIO_AUTH_TOKEN is missing")
            return PlainTextResponse(content="", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        form = await request.form()
        params = {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}

        if not signature or not _verify_twilio_signature(
            request_url=str(request.url),
            params=params,
            signature=signature,
            auth_token=settings.twilio_auth_token,
        ):
            logger.warning("Invalid Twilio signature for webhook request")
            return PlainTextResponse(content="", status_code=status.HTTP_403_FORBIDDEN)

    # Extract phone numbers early for trace context
    sender_phone = _extract_phone_number(From)
    our_number = _extract_phone_number(To)

    # Start trace context for this request
    correlation_id = start_trace_context(phone_number=sender_phone)
    logger.info(f"  TraceCorrelationId: {correlation_id}")

    try:
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

        # Save all pending traces before commit
        trace_count = await save_pending_traces(db)
        if trace_count > 0:
            logger.info(f"  Saved {trace_count} function traces")

        await db.commit()

        # Return empty TwiML (we send responses via the API, not TwiML)
        return PlainTextResponse(content="", media_type="text/xml")

    except Exception as e:
        logger.error(f"❌ Error processing Twilio webhook: {e}", exc_info=True)
        # Try to save traces even on error (for debugging)
        try:
            await save_pending_traces(db)
            await db.commit()
        except Exception:
            pass
        # Return empty response to avoid Twilio retries
        return PlainTextResponse(content="", media_type="text/xml")

    finally:
        # Clean up trace context
        clear_trace_context()


@router.get("/whatsapp/status", status_code=status.HTTP_200_OK)
async def webhook_status() -> dict[str, str]:
    """Health check endpoint for webhook configuration."""
    return {
        "status": "ok",
        "provider": "twilio",
        "whatsapp_number": settings.twilio_whatsapp_number or "not configured",
    }


@router.post("/twilio/sender-status", status_code=status.HTTP_200_OK)
async def receive_sender_status_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Receive Twilio sender status change notifications.

    Called when a WhatsApp sender transitions between states:
    CREATING → PENDING_VERIFICATION → VERIFYING → TWILIO_REVIEW → ONLINE

    Updates Organization.settings with current sender status.
    When status becomes ONLINE, the number is ready for WhatsApp.
    """
    try:
        data = await request.json()
    except Exception:
        # Twilio may send form-encoded data
        form = await request.form()
        data = dict(form)

    sender_sid = data.get("sid") or data.get("Sid")
    new_status = data.get("status") or data.get("Status")
    sender_id = data.get("senderId") or data.get("SenderId")  # Format: whatsapp:+525512345678

    # Extract phone number from senderId
    phone_number = None
    if sender_id:
        phone_number = (
            sender_id.replace("whatsapp:", "")
            if sender_id.startswith("whatsapp:")
            else sender_id
        )

    # Start trace context for this webhook
    start_trace_context(phone_number=phone_number or "unknown")

    try:
        logger.info(
            f"\n{'='*60}\n"
            f"📡 TWILIO SENDER STATUS WEBHOOK\n"
            f"{'='*60}\n"
            f"  SenderId: {sender_id}\n"
            f"  SenderSid: {sender_sid}\n"
            f"  Status: {new_status}\n"
            f"{'='*60}"
        )

        if phone_number:
            # Find org by provisioned number (stored in settings.twilio_phone_number)
            result = await db.execute(
                select(Organization).where(
                    Organization.settings["twilio_phone_number"].astext == phone_number
                )
            )
            org = result.scalar_one_or_none()

            if org:
                set_organization_id(org.id)
                logger.info(f"  Found org: {org.id} ({org.name})")

                settings_dict = dict(org.settings or {})
                settings_dict["sender_status"] = new_status
                settings_dict["sender_sid"] = sender_sid

                if new_status == "ONLINE":
                    # Number is ready for WhatsApp!
                    settings_dict["whatsapp_ready"] = True
                    settings_dict["number_status"] = "active"
                    org.whatsapp_phone_number_id = phone_number
                    logger.info(
                        f"  🎉 WhatsApp sender ONLINE! Org {org.id} is ready to receive messages"
                    )

                org.settings = settings_dict
                await save_pending_traces(db)
                await db.commit()
                logger.info(f"  Updated org settings with sender status: {new_status}")
            else:
                logger.warning(f"  No org found with twilio_phone_number: {phone_number}")
        else:
            logger.warning("  No senderId in webhook payload")

        return {"status": "received"}

    finally:
        clear_trace_context()
