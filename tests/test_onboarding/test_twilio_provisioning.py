"""Tests for Twilio provisioning service.

Tests for TwilioProvisioningService and the provision_number_for_business function.
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

            service = TwilioProvisioningService()
            assert service.is_configured is True

    def test_is_configured_without_account_sid(self):
        """Returns False when account_sid is missing."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = "auth_token_123"

            service = TwilioProvisioningService()
            assert service.is_configured is False

    def test_is_configured_without_auth_token(self):
        """Returns False when auth_token is missing."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = None

            service = TwilioProvisioningService()
            assert service.is_configured is False

    def test_is_configured_with_empty_strings(self):
        """Returns False when credentials are empty strings."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = ""
            mock_settings.twilio_auth_token = ""

            service = TwilioProvisioningService()
            assert service.is_configured is False


class TestListAvailableNumbers:
    """Tests for list_available_numbers method."""

    async def test_returns_available_numbers(self):
        """Returns list of available phone numbers from Twilio API."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

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

            service = TwilioProvisioningService()
            numbers = await service.list_available_numbers()

            assert numbers == []
            await service.close()

    async def test_returns_empty_list_on_http_error(self):
        """Returns empty list when Twilio API returns error."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

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

            service = TwilioProvisioningService()
            result = await service.purchase_number("+525512345678")

            assert result is None
            await service.close()

    async def test_returns_none_on_purchase_failure(self):
        """Returns None when purchase fails."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

            service = TwilioProvisioningService()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.side_effect = httpx.HTTPError("Purchase failed")

                result = await service.purchase_number("+525512345678")
                assert result is None

            await service.close()

    async def test_configures_webhook_during_purchase(self):
        """Webhook URL is set in purchase request."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.json.return_value = {"sid": "PN123", "phone_number": "+52555"}
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                await service.purchase_number(
                    phone_number="+525512345678",
                    webhook_url="https://api.yume.mx/api/v1/webhooks/whatsapp",
                )

                # Verify webhook URL was passed in data
                call_kwargs = mock_post.call_args[1]
                assert call_kwargs["data"]["SmsUrl"] == "https://api.yume.mx/api/v1/webhooks/whatsapp"

            await service.close()


class TestConfigureWebhook:
    """Tests for configure_webhook method."""

    async def test_configures_webhook_successfully(self):
        """Updates webhook URL for existing number."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

            service = TwilioProvisioningService()

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            with patch.object(
                service.client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                result = await service.configure_webhook(
                    phone_number_sid="PN123456",
                    webhook_url="https://new-api.yume.mx/webhooks",
                )

                assert result is True
                # Verify correct endpoint called
                call_args = mock_post.call_args
                assert "PN123456" in call_args[0][0]

            await service.close()

    async def test_returns_false_when_unconfigured(self):
        """Returns False when Twilio is not configured."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None

            service = TwilioProvisioningService()
            result = await service.configure_webhook("PN123", "https://test.com")

            assert result is False
            await service.close()


class TestReleaseNumber:
    """Tests for release_number method."""

    async def test_releases_number_successfully(self):
        """Releases number back to Twilio."""
        with patch("app.services.twilio_provisioning.settings") as mock_settings:
            mock_settings.twilio_account_sid = "AC123456"
            mock_settings.twilio_auth_token = "auth_token"

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

    async def test_provisions_complete_flow(self):
        """Lists, purchases, and returns number in one call."""
        with patch(
            "app.services.twilio_provisioning.TwilioProvisioningService"
        ) as MockService:
            mock_instance = MagicMock()
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
                country_code="MX",
            )

            assert result is not None
            assert result["phone_number"] == "+525512345678"
            assert result["phone_number_sid"] == "PN123456"

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
