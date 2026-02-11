"""Twilio number provisioning service.

This service handles provisioning dedicated WhatsApp numbers for businesses
using Twilio's WhatsApp Senders API (v2).

Flow:
1. Business completes onboarding via Parlo's main number
2. We purchase a phone number from Twilio
3. Register it as a WhatsApp sender under Parlo's WABA
4. Wait for sender status to become ONLINE (async via webhook)
5. (Future) Option to migrate their existing number
"""

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.services.tracing import traced

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioProvisioningError(Exception):
    """Error during Twilio provisioning."""
    pass


class TwilioProvisioningService:
    """Service for provisioning Twilio WhatsApp numbers using Senders API."""

    def __init__(self):
        """Initialize Twilio provisioning service."""
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.waba_id = settings.twilio_waba_id

        # API endpoints
        self.phone_numbers_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        )
        self.senders_url = "https://messaging.twilio.com/v2/Channels/Senders"

        self.client = httpx.AsyncClient(timeout=30.0)

    @property
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured for basic operations."""
        return bool(self.account_sid and self.auth_token)

    @property
    def is_whatsapp_configured(self) -> bool:
        """Check if Twilio is configured for WhatsApp Senders API."""
        return bool(self.is_configured and self.waba_id)

    @traced(trace_type="external_api", capture_args=["country_code", "area_code", "limit"])
    async def list_available_numbers(
        self,
        country_code: str = "US",
        area_code: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """List available phone numbers for purchase.

        Args:
            country_code: ISO country code (default: US)
            area_code: Optional area code filter
            limit: Max numbers to return

        Returns:
            List of available phone numbers with pricing
        """
        if not self.is_configured:
            logger.warning("Twilio not configured, returning empty list")
            return []

        number_type = "Local" if country_code == "US" else "Mobile"
        url = f"{self.phone_numbers_url}/AvailablePhoneNumbers/{country_code}/{number_type}.json"
        params = {"PageSize": limit}
        if area_code:
            params["AreaCode"] = area_code

        try:
            response = await self.client.get(
                url,
                params=params,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("available_phone_numbers", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list available numbers: {e}")
            return []

    @traced(trace_type="external_api", capture_args=["phone_number", "friendly_name", "country_code"])
    async def purchase_number(
        self,
        phone_number: str,
        friendly_name: str | None = None,
        webhook_url: str | None = None,
        country_code: str = "US",
    ) -> dict[str, Any] | None:
        """Purchase a phone number from Twilio.

        Args:
            phone_number: Phone number to purchase (E.164 format)
            friendly_name: Human-readable name for the number
            webhook_url: URL for incoming message webhooks (for SMS, not WhatsApp)
            country_code: ISO country code (US numbers skip regulatory bundle)

        Returns:
            Purchased number details or None on failure
        """
        if not self.is_configured:
            logger.warning("Twilio not configured, cannot purchase number")
            return None

        url = f"{self.phone_numbers_url}/IncomingPhoneNumbers.json"
        data = {"PhoneNumber": phone_number}

        if friendly_name:
            data["FriendlyName"] = friendly_name
        if webhook_url:
            data["SmsUrl"] = webhook_url
        # Non-US numbers (e.g. MX) require a verified address and regulatory bundle
        if country_code != "US":
            if settings.twilio_address_sid:
                data["AddressSid"] = settings.twilio_address_sid
            if settings.twilio_bundle_sid:
                data["BundleSid"] = settings.twilio_bundle_sid

        try:
            response = await self.client.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to purchase number: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    @traced(trace_type="external_api", capture_args=["phone_number", "business_name"])
    async def register_whatsapp_sender(
        self,
        phone_number: str,
        business_name: str,
        status_callback_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Register a phone number as WhatsApp sender under Parlo's WABA.

        Uses Twilio's Senders API (v2) to register the number for WhatsApp.

        Args:
            phone_number: Phone number in E.164 format (e.g., +525512345678)
            business_name: Display name for WhatsApp (must follow Meta guidelines)
            status_callback_url: Webhook for status updates (sender state changes)

        Returns:
            Sender details including sid, status, or None on failure
            Status will typically be PENDING_VERIFICATION or CREATING initially
        """
        if not self.is_whatsapp_configured:
            logger.warning(
                "Twilio WABA not configured, cannot register WhatsApp sender"
            )
            return None

        sender_id = f"whatsapp:{phone_number}"

        payload = {
            "SenderId": sender_id,
            "Configuration.WabaId": self.waba_id,
            "Configuration.Profile.Name": business_name,
        }

        if status_callback_url:
            payload["StatusCallbackUrl"] = status_callback_url

        try:
            response = await self.client.post(
                self.senders_url,
                data=payload,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"Registered WhatsApp sender: {sender_id}, "
                f"status={result.get('status')}, sid={result.get('sid')}"
            )
            return result
        except httpx.HTTPError as e:
            logger.error(f"Failed to register WhatsApp sender: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    @traced(trace_type="external_api", capture_args=["sender_sid"])
    async def get_sender_status(self, sender_sid: str) -> dict[str, Any] | None:
        """Get current status of a WhatsApp sender.

        Sender status values:
        - CREATING: Sender is being created
        - PENDING_VERIFICATION: Waiting for phone verification
        - VERIFYING: Verification in progress
        - TWILIO_REVIEW: Under Twilio review
        - ONLINE: Ready to send/receive messages
        - OFFLINE: Temporarily offline
        - DRAFT: Not yet submitted

        Args:
            sender_sid: The Twilio sender SID

        Returns:
            Sender details including current status, or None on failure
        """
        if not self.is_configured:
            return None

        url = f"{self.senders_url}/{sender_sid}"

        try:
            response = await self.client.get(
                url,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get sender status: {e}")
            return None

    @traced(trace_type="external_api", capture_args=["sender_sid"])
    async def submit_verification_code(
        self,
        sender_sid: str,
        verification_code: str,
    ) -> bool:
        """Submit SMS/voice verification code for a sender.

        Some sender registrations require phone verification. This method
        submits the verification code received via SMS or voice call.

        Args:
            sender_sid: The Twilio sender SID
            verification_code: The verification code received

        Returns:
            True if verification was submitted successfully
        """
        if not self.is_configured:
            return False

        url = f"{self.senders_url}/{sender_sid}"
        payload = {
            "Configuration.VerificationCode": verification_code,
        }

        try:
            response = await self.client.post(
                url,
                data=payload,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            logger.info(f"Submitted verification code for sender {sender_sid}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to submit verification code: {e}")
            return False

    @traced(trace_type="external_api", capture_args=["phone_number_sid"])
    async def configure_webhook(
        self,
        phone_number_sid: str,
        webhook_url: str,
    ) -> bool:
        """Configure webhook URL for a phone number (SMS only).

        Note: For WhatsApp, webhooks are configured at the sender level,
        not the phone number level.

        Args:
            phone_number_sid: Twilio phone number SID
            webhook_url: URL for incoming message webhooks

        Returns:
            True if successful
        """
        if not self.is_configured:
            return False

        url = f"{self.phone_numbers_url}/IncomingPhoneNumbers/{phone_number_sid}.json"
        data = {"SmsUrl": webhook_url}

        try:
            response = await self.client.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to configure webhook: {e}")
            return False

    @traced(trace_type="external_api", capture_args=["phone_number_sid"])
    async def release_number(self, phone_number_sid: str) -> bool:
        """Release (delete) a phone number.

        Args:
            phone_number_sid: Twilio phone number SID

        Returns:
            True if successful
        """
        if not self.is_configured:
            return False

        url = f"{self.phone_numbers_url}/IncomingPhoneNumbers/{phone_number_sid}.json"

        try:
            response = await self.client.delete(
                url,
                auth=(self.account_sid, self.auth_token),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to release number: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


@traced(capture_args=["business_name", "country_code"])
async def provision_number_for_business(
    business_name: str,
    webhook_base_url: str,
    country_code: str = "US",
) -> dict[str, Any] | None:
    """Provision a new phone number for a business and register for WhatsApp.

    This is a convenience function that:
    1. Lists available numbers
    2. Purchases the first available one
    3. Registers it as a WhatsApp sender under Parlo's WABA
    4. If sender registration fails, releases the purchased number (rollback)

    Args:
        business_name: Name of the business (for friendly name and WhatsApp profile)
        webhook_base_url: Base URL for webhooks (e.g., https://api.parlo.mx)
        country_code: Country code for the number

    Returns:
        Dict with phone_number, phone_number_sid, sender_sid, sender_status,
        or None on failure
    """
    service = TwilioProvisioningService()

    try:
        # Step 1: List available numbers
        available = await service.list_available_numbers(
            country_code=country_code,
            limit=1,
        )

        if not available:
            logger.error("No phone numbers available")
            return None

        # Step 2: Purchase the first available number
        number_to_buy = available[0]["phone_number"]
        purchased = await service.purchase_number(
            phone_number=number_to_buy,
            friendly_name=f"Parlo - {business_name}",
            webhook_url=f"{webhook_base_url}/api/v1/webhooks/whatsapp",
            country_code=country_code,
        )

        if not purchased:
            logger.error("Failed to purchase number")
            return None

        phone_number = purchased["phone_number"]
        phone_number_sid = purchased["sid"]
        logger.info(f"Purchased number: {phone_number} (SID: {phone_number_sid})")

        # Step 3: Register as WhatsApp sender (if WABA is configured)
        if service.is_whatsapp_configured:
            status_callback_url = (
                settings.twilio_senders_webhook_url
                or f"{webhook_base_url}/api/v1/webhooks/twilio/sender-status"
            )

            sender = await service.register_whatsapp_sender(
                phone_number=phone_number,
                business_name=business_name,
                status_callback_url=status_callback_url,
            )

            if not sender:
                # Rollback: release the purchased number
                logger.warning(
                    f"Failed to register WhatsApp sender, rolling back number purchase"
                )
                await service.release_number(phone_number_sid)
                return None

            return {
                "phone_number": phone_number,
                "phone_number_sid": phone_number_sid,
                "sender_sid": sender.get("sid"),
                "sender_status": sender.get("status"),
                "friendly_name": purchased.get("friendly_name"),
            }
        else:
            # WABA not configured - return without sender registration
            # This allows number purchase to work without WhatsApp setup
            logger.warning(
                "WABA not configured, number purchased but not registered for WhatsApp"
            )
            return {
                "phone_number": phone_number,
                "phone_number_sid": phone_number_sid,
                "sender_sid": None,
                "sender_status": None,
                "friendly_name": purchased.get("friendly_name"),
            }

    finally:
        await service.close()
