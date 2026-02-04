"""WhatsApp API client - handles sending messages via Twilio."""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppClient:
    """Client for Twilio WhatsApp API."""

    def __init__(self, mock_mode: bool = False):
        """Initialize WhatsApp client.

        Args:
            mock_mode: If True, don't actually call Twilio API (for testing)
        """
        self.mock_mode = mock_mode
        self.base_url = "https://api.twilio.com/2010-04-01"
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_whatsapp_number
        self.client = httpx.AsyncClient(timeout=30.0)

    def _format_whatsapp_number(self, phone: str) -> str:
        """Format phone number for Twilio WhatsApp.

        Args:
            phone: Phone number (with or without whatsapp: prefix)

        Returns:
            Formatted number with whatsapp: prefix
        """
        if phone.startswith("whatsapp:"):
            return phone
        # Ensure phone has + prefix
        if not phone.startswith("+"):
            phone = f"+{phone}"
        return f"whatsapp:{phone}"

    async def send_text_message(
        self,
        phone_number_id: str,
        to: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a text message via WhatsApp using Twilio.

        Args:
            phone_number_id: Phone number ID (used for routing, not for sending)
            to: Recipient's phone number
            message: Message content

        Returns:
            Response from Twilio API (or mock response)
        """
        if self.mock_mode:
            logger.info(
                f"📱 [MOCK] Sending WhatsApp message:\n"
                f"  From: {self.from_number}\n"
                f"  To: {to}\n"
                f"  Message: {message}"
            )
            return {
                "sid": f"mock_msg_{to}",
                "status": "queued",
                "to": to,
                "from": self.from_number,
            }

        return await self._send_via_twilio(to=to, message=message)

    async def _send_via_twilio(self, to: str, message: str) -> dict[str, Any]:
        """Send message via Twilio API (Yume's main number).

        Args:
            to: Recipient's phone number
            message: Message content

        Returns:
            Response from Twilio API
        """
        url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"

        # Format numbers for WhatsApp
        to_formatted = self._format_whatsapp_number(to)
        from_formatted = self._format_whatsapp_number(self.from_number)

        data = {
            "From": from_formatted,
            "To": to_formatted,
            "Body": message,
        }

        try:
            response = await self.client.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ Sent WhatsApp message via Twilio to {to} (SID: {result.get('sid')})")
            return result
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to send WhatsApp message via Twilio: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"   Response: {e.response.text}")
            raise

    async def send_template_message(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str = "es_MX",
        components: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send a template message via WhatsApp (Twilio).

        Note: Twilio uses Content Templates which work differently from Meta.
        For now, this sends a regular message. For production, configure
        Twilio Content Templates.

        Args:
            phone_number_id: Ignored for Twilio
            to: Recipient's phone number
            template_name: Template identifier (for Twilio Content API)
            language_code: Language code
            components: Template parameters

        Returns:
            Response from Twilio API (or mock response)
        """
        if self.mock_mode:
            logger.info(
                f"📱 [MOCK] Sending WhatsApp template:\n"
                f"  From: {self.from_number}\n"
                f"  To: {to}\n"
                f"  Template: {template_name}\n"
                f"  Components: {components}"
            )
            return {
                "sid": f"mock_template_{to}",
                "status": "queued",
                "to": to,
                "from": self.from_number,
            }

        # For Twilio Content Templates, you'd use ContentSid
        # For now, log a warning and send as regular message
        logger.warning(
            f"Template messages require Twilio Content Templates setup. "
            f"Sending '{template_name}' as regular message."
        )

        # Send as regular message (you should configure Content Templates for production)
        return await self.send_text_message(
            phone_number_id=phone_number_id,
            to=to,
            message=f"[Template: {template_name}]",
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
