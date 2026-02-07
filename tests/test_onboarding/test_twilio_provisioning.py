"""Tests for Twilio provisioning service.

Tests for TwilioProvisioningService with the Senders API and fallback strategy.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.twilio_provisioning import (
    TwilioProvisioningService,
    TwilioProvisioningError,
    provision_number_for_business,
)


pytestmark = pytest.mark.asyncio


class TestTwilioProvisioningServiceConfiguration:
    """Tests for TwilioProvisioningService configuration."""

    def test_is_configured_with_credentials(self):
        """Returns True when both account_sid and auth_token are set."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token_123"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()
            assert service.is_configured is True
            assert service.is_whatsapp_configured is False

    def test_is_configured_without_account_sid(self):
        """Returns False when account_sid is missing."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = "auth_token_123"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()
            assert service.is_configured is False
            assert service.is_whatsapp_configured is False

    def test_is_configured_without_auth_token(self):
        """Returns False when auth_token is missing."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()
            assert service.is_configured is False

    def test_is_configured_with_empty_strings(self):
        """Returns False when credentials are empty strings."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = ""
            mock_settings.twilio_auth_token = ""
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()
            assert service.is_configured is False

    def test_is_whatsapp_configured_with_waba_id(self):
        """Returns True when WABA ID is also configured."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token_123"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()
            assert service.is_configured is True
            assert service.is_whatsapp_configured is True


class TestListAvailableNumbers:
    """Tests for list_available_numbers method."""

    async def test_returns_available_numbers(self):
        """Returns list of available phone numbers from Twilio API."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "available_phone_numbers": [
                    {"phone_number": "+525512345678", "locality": "Mexico City"},
                    {"phone_number": "+525598765432", "locality": "Guadalajara"},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "get", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = mock_response

                numbers = await service.list_available_numbers(country_code="MX", limit=5)

                assert len(numbers) == 2
                assert numbers[0]["phone_number"] == "+525512345678"
                mock_get.assert_called_once()

            await service.close()

    async def test_returns_empty_list_when_unconfigured(self):
        """Returns empty list when Twilio is not configured."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()
            numbers = await service.list_available_numbers()

            assert numbers == []
            await service.close()

    async def test_returns_empty_list_on_http_error(self):
        """Returns empty list when Twilio API returns error."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "get", new_callable=AsyncMock
            ) as mock_get:
                mock_get.side_effect = httpx.HTTPError("Connection error")

                numbers = await service.list_available_numbers()
                assert numbers == []

            await service.close()

    async def test_passes_area_code_filter(self):
        """Passes area code filter to Twilio API."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {"available_phone_numbers": []}
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "get", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = mock_response

                await service.list_available_numbers(country_code="MX", area_code="55")

                # Verify area code was passed in params
                call_kwargs = mock_get.call_args[1]
                assert call_kwargs["params"]["AreaCode"] == "55"

            await service.close()


class TestPurchaseNumber:
    """Tests for purchase_number method."""

    async def test_purchases_number_successfully(self):
        """Purchases phone number and returns details."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "sid": "PN123456789",
                "phone_number": "+525512345678",
                "friendly_name": "Yume - Test Business",
            }
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                result = await service.purchase_number(
                    phone_number="+525512345678",
                    friendly_name="Yume - Test Business",
                    webhook_url="https://api.yume.mx/webhooks/whatsapp",
                )

                assert result["sid"] == "PN123456789"
                assert result["phone_number"] == "+525512345678"

            await service.close()

    async def test_returns_none_when_unconfigured(self):
        """Returns None when Twilio is not configured."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()
            result = await service.purchase_number("+525512345678")

            assert result is None
            await service.close()

    async def test_returns_none_on_purchase_failure(self):
        """Returns None when purchase fails."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.side_effect = httpx.HTTPError("Purchase failed")

                result = await service.purchase_number("+525512345678")
                assert result is None

            await service.close()


class TestRegisterWhatsAppSender:
    """Tests for register_whatsapp_sender method."""

    async def test_registers_sender_successfully(self):
        """Registers WhatsApp sender with Senders API."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "sid": "XE123456789",
                "status": "PENDING_VERIFICATION",
                "sender_id": "whatsapp:+525512345678",
            }
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                result = await service.register_whatsapp_sender(
                    phone_number="+525512345678",
                    business_name="Test Salon",
                    status_callback_url="https://api.yume.mx/webhooks/sender-status",
                )

                assert result["sid"] == "XE123456789"
                assert result["status"] == "PENDING_VERIFICATION"

                # Verify correct API was called
                call_args = mock_post.call_args
                assert "Senders" in call_args[0][0]

            await service.close()

    async def test_returns_none_when_waba_not_configured(self):
        """Returns None when WABA ID is not configured."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""  # Not configured

            service = TwilioProvisioningService()
            result = await service.register_whatsapp_sender(
                phone_number="+525512345678",
                business_name="Test Salon",
            )

            assert result is None
            await service.close()

    async def test_returns_none_on_api_error(self):
        """Returns None when Senders API returns error."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.side_effect = httpx.HTTPError("API error")

                result = await service.register_whatsapp_sender(
                    phone_number="+525512345678",
                    business_name="Test Salon",
                )
                assert result is None

            await service.close()


class TestGetSenderStatus:
    """Tests for get_sender_status method."""

    async def test_gets_sender_status_successfully(self):
        """Gets current sender status."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "sid": "XE123456789",
                "status": "ONLINE",
                "sender_id": "whatsapp:+525512345678",
            }
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "get", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = mock_response

                result = await service.get_sender_status("XE123456789")

                assert result["status"] == "ONLINE"

            await service.close()

    async def test_returns_none_on_error(self):
        """Returns None when API call fails."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = "waba123"

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "get", new_callable=AsyncMock
            ) as mock_get:
                mock_get.side_effect = httpx.HTTPError("Not found")

                result = await service.get_sender_status("XE123456789")
                assert result is None

            await service.close()


class TestReleaseNumber:
    """Tests for release_number method."""

    async def test_releases_number_successfully(self):
        """Releases number back to Twilio."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "delete", new_callable=AsyncMock
            ) as mock_delete:
                mock_delete.return_value = mock_response

                result = await service.release_number("PN123456")

                assert result is True
                mock_delete.assert_called_once()

            await service.close()

    async def test_returns_false_on_release_failure(self):
        """Returns False when release fails."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"
            mock_settings.twilio_waba_id = ""

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "delete", new_callable=AsyncMock
            ) as mock_delete:
                mock_delete.side_effect = httpx.HTTPError("Delete failed")

                result = await service.release_number("PN123456")
                assert result is False

            await service.close()


class TestProvisionNumberForBusiness:
    """Tests for provision_number_for_business convenience function."""

    async def test_provisions_complete_flow_with_sender(self):
        """Lists, purchases, registers sender in one call."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = True
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={
                    "sid": "PN123456",
                    "phone_number": "+525512345678",
                    "friendly_name": "Yume - Test Salon",
                }
            )
            mock_instance.register_whatsapp_sender = AsyncMock(
                return_value={
                    "sid": "XE789",
                    "status": "PENDING_VERIFICATION",
                }
            )
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            with patch("app.services.twilio_provisioning.settings") as mock_settings:
                mock_settings.twilio_senders_webhook_url = "https://test.com/webhook"

                result = await provision_number_for_business(
                    business_name="Test Salon",
                    webhook_base_url="https://api.yume.mx",
                    country_code="MX",
                )

            assert result is not None
            assert result["phone_number"] == "+525512345678"
            assert result["phone_number_sid"] == "PN123456"
            assert result["sender_sid"] == "XE789"
            assert result["sender_status"] == "PENDING_VERIFICATION"

    async def test_provisions_without_waba_configured(self):
        """Provisions number without sender registration when WABA not configured."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = False  # WABA not configured
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={
                    "sid": "PN123456",
                    "phone_number": "+525512345678",
                    "friendly_name": "Yume - Test Salon",
                }
            )
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            result = await provision_number_for_business(
                business_name="Test Salon",
                webhook_base_url="https://api.yume.mx",
            )

            assert result is not None
            assert result["phone_number"] == "+525512345678"
            assert result["sender_sid"] is None
            assert result["sender_status"] is None

    async def test_rollback_on_sender_registration_failure(self):
        """Releases purchased number if sender registration fails."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = True
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={
                    "sid": "PN123456",
                    "phone_number": "+525512345678",
                    "friendly_name": "Yume - Test Salon",
                }
            )
            mock_instance.register_whatsapp_sender = AsyncMock(return_value=None)
            mock_instance.release_number = AsyncMock(return_value=True)
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            with patch("app.services.twilio_provisioning.settings") as mock_settings:
                mock_settings.twilio_senders_webhook_url = ""

                result = await provision_number_for_business(
                    business_name="Test Salon",
                    webhook_base_url="https://api.yume.mx",
                )

            assert result is None
            # Verify rollback was called
            mock_instance.release_number.assert_called_once_with("PN123456")

    async def test_returns_none_when_no_numbers_available(self):
        """Returns None if no numbers available."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.list_available_numbers = AsyncMock(return_value=[])
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            result = await provision_number_for_business(
                business_name="Test Salon",
                webhook_base_url="https://api.yume.mx",
            )

            assert result is None

    async def test_returns_none_on_purchase_failure(self):
        """Returns None if purchase fails."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(return_value=None)
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            result = await provision_number_for_business(
                business_name="Test Salon",
                webhook_base_url="https://api.yume.mx",
            )

            assert result is None

    async def test_webhook_url_format_correct(self):
        """Webhook URL follows pattern: {base}/api/v1/webhooks/whatsapp."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = False
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={
                    "sid": "PN123456",
                    "phone_number": "+525512345678",
                    "friendly_name": "Yume - Test",
                }
            )
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            await provision_number_for_business(
                business_name="Test Salon",
                webhook_base_url="https://api.yume.mx",
            )

            # Verify webhook URL format
            purchase_call = mock_instance.purchase_number.call_args
            assert purchase_call[1]["webhook_url"] == "https://api.yume.mx/api/v1/webhooks/whatsapp"

    async def test_friendly_name_includes_business_name(self):
        """Friendly name includes 'Yume - {business_name}'."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = False
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={
                    "sid": "PN123456",
                    "phone_number": "+525512345678",
                    "friendly_name": "Yume - Salón Bella",
                }
            )
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            await provision_number_for_business(
                business_name="Salón Bella",
                webhook_base_url="https://api.yume.mx",
            )

            # Verify friendly name format
            purchase_call = mock_instance.purchase_number.call_args
            assert purchase_call[1]["friendly_name"] == "Yume - Salón Bella"

    async def test_closes_service_on_success(self):
        """Service is closed after successful provisioning."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.is_whatsapp_configured = False
            mock_instance.list_available_numbers = AsyncMock(
                return_value=[{"phone_number": "+525512345678"}]
            )
            mock_instance.purchase_number = AsyncMock(
                return_value={"sid": "PN123", "phone_number": "+52555"}
            )
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            await provision_number_for_business(
                business_name="Test",
                webhook_base_url="https://test.com",
            )

            mock_instance.close.assert_called_once()

    async def test_closes_service_on_failure(self):
        """Service is closed even when provisioning fails."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.list_available_numbers = AsyncMock(return_value=[])
            mock_instance.close = AsyncMock()
            MockService.return_value = mock_instance

            await provision_number_for_business(
                business_name="Test",
                webhook_base_url="https://test.com",
            )

            mock_instance.close.assert_called_once()
