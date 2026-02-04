"""Unit tests for onboarding tool execution.

Tests individual tools in the OnboardingHandler._execute_tool method.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.models import OnboardingSession, OnboardingState
from app.services.onboarding import OnboardingHandler


pytestmark = pytest.mark.asyncio


class TestSaveBusinessInfoTool:
    """Tests for save_business_info tool."""

    async def test_saves_basic_business_info(
        self, db, onboarding_session_initiated
    ):
        """save_business_info stores business name, type, and owner."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Salón Bella",
                "business_type": "salon",
                "owner_name": "Maria García",
            },
        )

        assert result["success"] is True
        assert result["business_name"] == "Salón Bella"
        assert result["owner_name"] == "Maria García"

        # Verify data was stored in session
        await db.refresh(onboarding_session_initiated)
        assert onboarding_session_initiated.collected_data["business_name"] == "Salón Bella"
        assert onboarding_session_initiated.collected_data["business_type"] == "salon"
        assert onboarding_session_initiated.collected_data["owner_name"] == "Maria García"

    async def test_saves_optional_address_and_city(
        self, db, onboarding_session_initiated
    ):
        """save_business_info stores optional address and city."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Barbería Don Carlos",
                "business_type": "barbershop",
                "owner_name": "Carlos Rodríguez",
                "address": "Av. Reforma 123",
                "city": "CDMX",
            },
        )

        assert result["success"] is True

        await db.refresh(onboarding_session_initiated)
        assert onboarding_session_initiated.collected_data["address"] == "Av. Reforma 123"
        assert onboarding_session_initiated.collected_data["city"] == "CDMX"

    async def test_transitions_state_to_collecting_services(
        self, db, onboarding_session_initiated
    ):
        """save_business_info transitions state to COLLECTING_SERVICES."""
        handler = OnboardingHandler(db=db)

        await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Spa Zen",
                "business_type": "spa",
                "owner_name": "Ana López",
            },
        )

        await db.refresh(onboarding_session_initiated)
        assert onboarding_session_initiated.state == OnboardingState.COLLECTING_SERVICES.value


class TestAddServiceTool:
    """Tests for add_service tool."""

    async def test_adds_first_service(
        self, db, onboarding_session_collecting_services
    ):
        """add_service creates services array and adds first service."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="add_service",
            tool_input={
                "name": "Corte de cabello",
                "duration_minutes": 30,
                "price": 150,
            },
        )

        assert result["success"] is True
        assert result["total_services"] == 1
        assert "Corte de cabello" in result["message"]

        await db.refresh(onboarding_session_collecting_services)
        services = onboarding_session_collecting_services.collected_data["services"]
        assert len(services) == 1
        assert services[0]["name"] == "Corte de cabello"
        assert services[0]["duration_minutes"] == 30
        assert services[0]["price"] == 150

    async def test_adds_multiple_services(
        self, db, onboarding_session_collecting_services
    ):
        """add_service can add multiple services sequentially."""
        handler = OnboardingHandler(db=db)

        # Add first service
        await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="add_service",
            tool_input={"name": "Corte", "duration_minutes": 30, "price": 150},
        )

        # Add second service
        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="add_service",
            tool_input={"name": "Tinte", "duration_minutes": 90, "price": 500},
        )

        assert result["total_services"] == 2

        await db.refresh(onboarding_session_collecting_services)
        services = onboarding_session_collecting_services.collected_data["services"]
        assert len(services) == 2

    async def test_returns_menu_display(
        self, db, onboarding_session_collecting_services
    ):
        """add_service returns formatted menu for display."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="add_service",
            tool_input={"name": "Manicure", "duration_minutes": 45, "price": 200},
        )

        assert "menu_display" in result
        assert "Manicure" in result["menu_display"]
        assert "$200" in result["menu_display"]
        assert "45 min" in result["menu_display"]


class TestGetCurrentMenuTool:
    """Tests for get_current_menu tool."""

    async def test_returns_empty_menu_message(
        self, db, onboarding_session_collecting_services
    ):
        """get_current_menu returns 'no services' message when empty."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="get_current_menu",
            tool_input={},
        )

        assert result["success"] is True
        assert result["total_services"] == 0
        assert result["menu_display"] == "Sin servicios aún"

    async def test_returns_formatted_menu(
        self, db, onboarding_session_with_services
    ):
        """get_current_menu returns formatted list of services."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="get_current_menu",
            tool_input={},
        )

        assert result["success"] is True
        assert result["total_services"] == 2
        assert "Corte de cabello" in result["menu_display"]
        assert "Corte y barba" in result["menu_display"]


class TestAddStaffMemberTool:
    """Tests for add_staff_member tool."""

    async def test_adds_staff_member(
        self, db, onboarding_session_with_services
    ):
        """add_staff_member adds employee to staff list."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="add_staff_member",
            tool_input={
                "name": "Pedro",
                "phone_number": "5512345678",
            },
        )

        assert result["success"] is True
        assert "Pedro" in result["message"]

        await db.refresh(onboarding_session_with_services)
        staff = onboarding_session_with_services.collected_data["staff"]
        assert len(staff) == 1
        assert staff[0]["name"] == "Pedro"

    async def test_normalizes_phone_number_without_country_code(
        self, db, onboarding_session_with_services
    ):
        """add_staff_member adds +52 prefix to numbers without it."""
        handler = OnboardingHandler(db=db)

        await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="add_staff_member",
            tool_input={
                "name": "Maria",
                "phone_number": "5598765432",
            },
        )

        await db.refresh(onboarding_session_with_services)
        staff = onboarding_session_with_services.collected_data["staff"]
        assert staff[0]["phone_number"] == "+525598765432"

    async def test_normalizes_phone_number_with_country_code(
        self, db, onboarding_session_with_services
    ):
        """add_staff_member adds + prefix to numbers with country code."""
        handler = OnboardingHandler(db=db)

        await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="add_staff_member",
            tool_input={
                "name": "Carlos",
                "phone_number": "525512345678",
            },
        )

        await db.refresh(onboarding_session_with_services)
        staff = onboarding_session_with_services.collected_data["staff"]
        assert staff[0]["phone_number"] == "+525512345678"

    async def test_stores_specific_services(
        self, db, onboarding_session_with_services
    ):
        """add_staff_member stores service specializations."""
        handler = OnboardingHandler(db=db)

        await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="add_staff_member",
            tool_input={
                "name": "Luis",
                "phone_number": "5511111111",
                "services": ["Corte de cabello"],
            },
        )

        await db.refresh(onboarding_session_with_services)
        staff = onboarding_session_with_services.collected_data["staff"]
        assert staff[0]["services"] == ["Corte de cabello"]


class TestSaveBusinessHoursTool:
    """Tests for save_business_hours tool."""

    async def test_saves_full_week_hours(
        self, db, onboarding_session_with_services
    ):
        """save_business_hours stores complete week schedule."""
        handler = OnboardingHandler(db=db)

        hours = {
            "monday": {"open": "09:00", "close": "19:00"},
            "tuesday": {"open": "09:00", "close": "19:00"},
            "wednesday": {"open": "09:00", "close": "19:00"},
            "thursday": {"open": "09:00", "close": "19:00"},
            "friday": {"open": "09:00", "close": "19:00"},
            "saturday": {"open": "09:00", "close": "15:00"},
            "sunday": {"closed": True},
        }

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="save_business_hours",
            tool_input=hours,
        )

        assert result["success"] is True

        await db.refresh(onboarding_session_with_services)
        saved_hours = onboarding_session_with_services.collected_data["business_hours"]
        assert saved_hours["monday"]["open"] == "09:00"
        assert saved_hours["sunday"]["closed"] is True

    async def test_saves_partial_hours(
        self, db, onboarding_session_with_services
    ):
        """save_business_hours stores partial week schedule."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="save_business_hours",
            tool_input={
                "monday": {"open": "10:00", "close": "18:00"},
                "friday": {"open": "10:00", "close": "20:00"},
            },
        )

        assert result["success"] is True

        await db.refresh(onboarding_session_with_services)
        saved_hours = onboarding_session_with_services.collected_data["business_hours"]
        assert "monday" in saved_hours
        assert "friday" in saved_hours
        assert "tuesday" not in saved_hours  # Only specified days saved


class TestCompleteOnboardingTool:
    """Tests for complete_onboarding tool."""

    async def test_requires_confirmation(
        self, db, onboarding_session_ready_for_completion
    ):
        """complete_onboarding fails without user confirmation."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_ready_for_completion,
            tool_name="complete_onboarding",
            tool_input={"confirmed": False},
        )

        assert result["success"] is False
        assert "no confirmó" in result["message"]

    async def test_requires_business_name(
        self, db, onboarding_session_initiated
    ):
        """complete_onboarding fails without business name."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        assert result["success"] is False
        assert "nombre del negocio" in result["error"]

    async def test_requires_at_least_one_service(
        self, db, onboarding_session_collecting_services
    ):
        """complete_onboarding fails without any services."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        assert result["success"] is False
        assert "servicio" in result["error"]

    async def test_creates_organization_on_success(
        self, db, onboarding_session_ready_for_completion
    ):
        """complete_onboarding creates organization and related entities."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_ready_for_completion,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        assert result["success"] is True
        assert "organization_id" in result
        assert result["business_name"] == "Spa Relajación"

        # Verify session state updated
        await db.refresh(onboarding_session_ready_for_completion)
        assert onboarding_session_ready_for_completion.state == OnboardingState.COMPLETED.value
        assert onboarding_session_ready_for_completion.organization_id is not None

    async def test_creates_organization_with_twilio_number(
        self, db, onboarding_session_with_twilio_number
    ):
        """complete_onboarding uses Twilio phone number (not SID) for whatsapp_phone_number_id."""
        from tests.test_onboarding.conftest import verify_organization_created

        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_twilio_number,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        assert result["success"] is True

        # Verify the organization was created with correct whatsapp_phone_number_id
        org = await verify_organization_created(
            db=db,
            phone_number="+525555556666",
            expected_business_name="Barbería Don Pedro",
            expected_whatsapp_number="+525512345678",  # Phone number, not SID
        )

        # Verify SID is stored in settings
        assert org.settings["twilio_phone_number_sid"] == "PN123456789"


class TestProvisionTwilioNumberTool:
    """Tests for provision_twilio_number tool."""

    async def test_requires_business_name(
        self, db, onboarding_session_initiated
    ):
        """provision_twilio_number fails without business name."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="provision_twilio_number",
            tool_input={},
        )

        assert result["success"] is False
        assert "nombre del negocio" in result["error"]

    async def test_requires_at_least_one_service(
        self, db, onboarding_session_collecting_services
    ):
        """provision_twilio_number fails without services."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_collecting_services,
            tool_name="provision_twilio_number",
            tool_input={},
        )

        assert result["success"] is False
        assert "servicio" in result["error"]

    async def test_provisions_number_successfully(
        self, db, onboarding_session_with_services
    ):
        """provision_twilio_number provisions and stores number."""
        handler = OnboardingHandler(db=db)

        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+525512345678",
                "phone_number_sid": "PN987654321",
                "friendly_name": "Yume - Barbería Don Juan",
            }

            result = await handler._execute_tool(
                session=onboarding_session_with_services,
                tool_name="provision_twilio_number",
                tool_input={"country_code": "MX"},
            )

            assert result["success"] is True
            assert result["phone_number"] == "+525512345678"

            # Verify stored in session
            await db.refresh(onboarding_session_with_services)
            collected = onboarding_session_with_services.collected_data
            assert collected["twilio_provisioned_number"] == "+525512345678"
            assert collected["twilio_phone_number_sid"] == "PN987654321"

    async def test_handles_provisioning_failure(
        self, db, onboarding_session_with_services
    ):
        """provision_twilio_number handles Twilio API failure."""
        handler = OnboardingHandler(db=db)

        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = None  # Simulate failure

            result = await handler._execute_tool(
                session=onboarding_session_with_services,
                tool_name="provision_twilio_number",
                tool_input={},
            )

            assert result["success"] is False
            assert "fallback_message" in result

    async def test_uses_country_code_parameter(
        self, db, onboarding_session_with_services
    ):
        """provision_twilio_number passes country code to provisioning service."""
        handler = OnboardingHandler(db=db)

        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+15551234567",
                "phone_number_sid": "PN111111",
                "friendly_name": "Yume - Test",
            }

            await handler._execute_tool(
                session=onboarding_session_with_services,
                tool_name="provision_twilio_number",
                tool_input={"country_code": "US"},
            )

            # Verify country code was passed
            mock_provision.assert_called_once()
            call_kwargs = mock_provision.call_args[1]
            assert call_kwargs["country_code"] == "US"


class TestSendDashboardLinkTool:
    """Tests for send_dashboard_link tool."""

    async def test_returns_dashboard_url(
        self, db, onboarding_session_with_services
    ):
        """send_dashboard_link returns dashboard URL."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="send_dashboard_link",
            tool_input={},
        )

        assert result["success"] is True
        assert "dashboard_url" in result
        assert "/login" in result["dashboard_url"]
        assert result["business_name"] == "Barbería Don Juan"

    async def test_includes_login_instructions(
        self, db, onboarding_session_with_services
    ):
        """send_dashboard_link includes login instructions."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_with_services,
            tool_name="send_dashboard_link",
            tool_input={},
        )

        assert "login_instructions" in result
        assert "WhatsApp" in result["login_instructions"]


class TestUnknownTool:
    """Tests for unknown tool handling."""

    async def test_returns_error_for_unknown_tool(
        self, db, onboarding_session_initiated
    ):
        """Unknown tool names return error."""
        handler = OnboardingHandler(db=db)

        result = await handler._execute_tool(
            session=onboarding_session_initiated,
            tool_name="nonexistent_tool",
            tool_input={},
        )

        assert "error" in result
        assert "Unknown tool" in result["error"]
