"""End-to-end tests for onboarding flow with Twilio provisioning.

These tests verify the complete onboarding flow from first message
through organization creation and subsequent message routing.
"""

import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models import (
    OnboardingSession,
    OnboardingState,
    Organization,
    YumeUser,
    YumeUserRole,
    ServiceType,
    Location,
)

# Aliases for readability
Staff = YumeUser
StaffRole = YumeUserRole
from app.services.message_router import MessageRouter
from app.services.onboarding import OnboardingHandler

from tests.test_onboarding.conftest import (
    MockOpenAIClient,
    verify_organization_created,
    verify_staff_created,
    verify_services_created,
)


pytestmark = pytest.mark.asyncio


class TestOnboardingE2EWithTwilioProvisioning:
    """End-to-end tests including Twilio number provisioning."""

    async def test_complete_onboarding_with_twilio_number(
        self, db, mock_whatsapp_client
    ):
        """
        Full flow:
        1. User texts Yume Central: "Hola"
        2. Onboarding conversation collects business info + services
        3. User chooses Twilio provisioning
        4. Number provisioned (mocked Twilio API)
        5. Organization created with whatsapp_phone_number_id = provisioned number
        6. Verify message to provisioned number routes to this org
        """
        handler = OnboardingHandler(db=db)

        # Step 1: Create session
        session = await handler.get_or_create_session(
            phone_number="+525599998888",
            sender_name="Roberto",
        )
        assert session.state == OnboardingState.INITIATED.value

        # Step 2: Save business info
        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Barbería El Patrón",
                "business_type": "barbershop",
                "owner_name": "Roberto García",
            },
        )
        await db.refresh(session)
        assert session.state == OnboardingState.COLLECTING_SERVICES.value

        # Step 3: Add services
        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Corte clásico", "duration_minutes": 30, "price": 120},
        )
        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Corte y barba", "duration_minutes": 45, "price": 180},
        )

        # Step 4: Provision Twilio number
        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+525588887777",
                "phone_number_sid": "PN_ROBERTO_001",
                "friendly_name": "Yume - Barbería El Patrón",
            }

            result = await handler._execute_tool(
                session=session,
                tool_name="provision_twilio_number",
                tool_input={"country_code": "MX"},
            )

            assert result["success"] is True
            assert result["phone_number"] == "+525588887777"

        # Step 5: Complete onboarding
        result = await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        assert result["success"] is True

        # Step 6: Verify organization was created correctly
        org = await verify_organization_created(
            db=db,
            phone_number="+525599998888",
            expected_business_name="Barbería El Patrón",
            expected_whatsapp_number="+525588887777",  # Phone number, NOT SID
        )

        # Verify SID stored in settings
        assert org.settings["twilio_phone_number_sid"] == "PN_ROBERTO_001"
        assert org.settings["whatsapp_provider"] == "twilio"

        # Verify staff (owner) was created
        await verify_staff_created(
            db=db,
            organization_id=org.id,
            phone_number="+525599998888",
            expected_name="Roberto García",
            expected_role=StaffRole.OWNER.value,
        )

        # Verify services were created
        services = await verify_services_created(
            db=db,
            organization_id=org.id,
            expected_count=2,
        )
        service_names = [s.name for s in services]
        assert "Corte clásico" in service_names
        assert "Corte y barba" in service_names

    async def test_message_routes_to_new_business_after_onboarding(
        self, db, mock_whatsapp_client
    ):
        """
        After onboarding with Twilio number:
        1. Complete onboarding with Twilio provisioning
        2. Customer sends message to business's new number
        3. Message routes to customer flow (Case 5)
        """
        # Setup: Complete onboarding first
        handler = OnboardingHandler(db=db)

        session = await handler.get_or_create_session(
            phone_number="+525511112222",
            sender_name="Sofia",
        )

        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Salón Sofia",
                "business_type": "salon",
                "owner_name": "Sofia Martínez",
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Corte dama", "duration_minutes": 45, "price": 250},
        )

        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+525566667777",
                "phone_number_sid": "PN_SOFIA_001",
            }

            await handler._execute_tool(
                session=session,
                tool_name="provision_twilio_number",
                tool_input={},
            )

        await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        await db.commit()

        # Now test: Customer message to the new business number
        router = MessageRouter(db=db, whatsapp_client=mock_whatsapp_client)

        with patch(
            "app.services.customer_flows.CustomerFlowHandler.handle_message",
            new_callable=AsyncMock,
        ) as mock_customer_handler:
            mock_customer_handler.return_value = "¡Hola! ¿Te gustaría agendar una cita?"

            result = await router.route_message(
                phone_number_id="+525566667777",  # The provisioned number
                sender_phone="+525533334444",  # A customer
                message_id="customer_msg_001",
                message_content="Hola, quiero una cita para mañana",
                sender_name="Cliente",
            )

            assert result["status"] == "success"
            assert result["case"] == "5"  # End customer flow
            assert result["sender_type"] == "customer"

            # Verify it routed to the correct organization
            org_result = await db.execute(
                select(Organization).where(
                    Organization.whatsapp_phone_number_id == "+525566667777"
                )
            )
            org = org_result.scalar_one()
            assert result["organization_id"] == str(org.id)
            assert org.name == "Salón Sofia"

    async def test_owner_message_to_new_business_routes_to_staff_flow(
        self, db, mock_whatsapp_client
    ):
        """
        After onboarding:
        1. Owner sends message to their business number
        2. Message routes to staff flow (Case 4)
        3. Can manage bookings
        """
        # Setup: Complete onboarding first
        handler = OnboardingHandler(db=db)

        session = await handler.get_or_create_session(
            phone_number="+525544445555",
            sender_name="Miguel",
        )

        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Barbería Don Miguel",
                "business_type": "barbershop",
                "owner_name": "Miguel López",
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Corte", "duration_minutes": 30, "price": 100},
        )

        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+525577778888",
                "phone_number_sid": "PN_MIGUEL_001",
            }

            await handler._execute_tool(
                session=session,
                tool_name="provision_twilio_number",
                tool_input={},
            )

        await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        # Mark owner as having sent first message (to bypass staff onboarding)
        staff_result = await db.execute(
            select(Staff).where(Staff.phone_number == "+525544445555")
        )
        staff = staff_result.scalar_one()
        staff.first_message_at = "2024-01-01T00:00:00Z"
        await db.commit()

        # Now test: Owner message to their business number
        router = MessageRouter(db=db, whatsapp_client=mock_whatsapp_client)

        with patch(
            "app.services.conversation.ConversationHandler.handle_staff_message",
            new_callable=AsyncMock,
        ) as mock_staff_handler:
            mock_staff_handler.return_value = "Tienes 3 citas hoy..."

            result = await router.route_message(
                phone_number_id="+525577778888",  # Business's provisioned number
                sender_phone="+525544445555",  # Owner's phone (same as registration)
                message_id="owner_msg_001",
                message_content="Mi agenda de hoy",
                sender_name="Miguel",
            )

            assert result["status"] == "success"
            assert result["case"] == "4"  # Staff flow
            assert result["sender_type"] == "staff"

    async def test_organization_has_correct_whatsapp_phone_number_id(
        self, db
    ):
        """
        Verify the bug fix: whatsapp_phone_number_id should be the phone number,
        not the Twilio SID.
        """
        handler = OnboardingHandler(db=db)

        session = await handler.get_or_create_session(
            phone_number="+525500001111",
            sender_name="Test",
        )

        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Test Business",
                "business_type": "salon",
                "owner_name": "Test Owner",
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Service", "duration_minutes": 30, "price": 100},
        )

        # Provision with a clearly different SID vs phone number
        with patch(
            "app.services.onboarding.provision_number_for_business",
            new_callable=AsyncMock,
        ) as mock_provision:
            mock_provision.return_value = {
                "phone_number": "+525522223333",  # The actual phone number
                "phone_number_sid": "PN_TEST_UNIQUE_SID_12345",  # The SID
            }

            await handler._execute_tool(
                session=session,
                tool_name="provision_twilio_number",
                tool_input={},
            )

        await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        # Verify
        org_result = await db.execute(
            select(Organization).where(Organization.phone_number == "+525500001111")
        )
        org = org_result.scalar_one()

        # THE KEY ASSERTION: whatsapp_phone_number_id should be the phone number
        assert org.whatsapp_phone_number_id == "+525522223333"
        assert org.whatsapp_phone_number_id != "PN_TEST_UNIQUE_SID_12345"

        # SID should be stored separately in settings
        assert org.settings["twilio_phone_number_sid"] == "PN_TEST_UNIQUE_SID_12345"

    async def test_onboarding_without_twilio_uses_owner_phone(
        self, db
    ):
        """
        When onboarding completes without Twilio provisioning,
        whatsapp_phone_number_id should use owner's phone as placeholder.
        """
        handler = OnboardingHandler(db=db)

        session = await handler.get_or_create_session(
            phone_number="+525588889999",
            sender_name="Elena",
        )

        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Spa Elena",
                "business_type": "spa",
                "owner_name": "Elena Ruiz",
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Masaje", "duration_minutes": 60, "price": 500},
        )

        # Complete WITHOUT provisioning Twilio number
        await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        org_result = await db.execute(
            select(Organization).where(Organization.phone_number == "+525588889999")
        )
        org = org_result.scalar_one()

        # Should use owner's phone as placeholder
        assert org.whatsapp_phone_number_id == "+525588889999"
        assert org.settings["whatsapp_provider"] == "pending"


class TestOnboardingE2EWithStaff:
    """Tests for onboarding with additional staff members."""

    async def test_creates_additional_staff_members(
        self, db
    ):
        """Onboarding creates additional staff members correctly."""
        handler = OnboardingHandler(db=db)

        session = await handler.get_or_create_session(
            phone_number="+525599990000",
            sender_name="Carmen",
        )

        await handler._execute_tool(
            session=session,
            tool_name="save_business_info",
            tool_input={
                "business_name": "Salón Carmen",
                "business_type": "salon",
                "owner_name": "Carmen Vega",
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Corte", "duration_minutes": 45, "price": 250},
        )
        await handler._execute_tool(
            session=session,
            tool_name="add_service",
            tool_input={"name": "Tinte", "duration_minutes": 120, "price": 800},
        )

        # Add staff members
        await handler._execute_tool(
            session=session,
            tool_name="add_staff_member",
            tool_input={
                "name": "Ana",
                "phone_number": "5512345678",
                "services": ["Corte"],  # Only does cuts
            },
        )
        await handler._execute_tool(
            session=session,
            tool_name="add_staff_member",
            tool_input={
                "name": "Beto",
                "phone_number": "5598765432",
                # No services specified = does all
            },
        )

        await handler._execute_tool(
            session=session,
            tool_name="complete_onboarding",
            tool_input={"confirmed": True},
        )

        # Verify staff were created
        org_result = await db.execute(
            select(Organization).where(Organization.phone_number == "+525599990000")
        )
        org = org_result.scalar_one()

        staff_result = await db.execute(
            select(Staff).where(Staff.organization_id == org.id)
        )
        staff_list = staff_result.scalars().all()

        assert len(staff_list) == 3  # Owner + 2 employees

        # Verify owner
        owner = next((s for s in staff_list if s.role == StaffRole.OWNER.value), None)
        assert owner is not None
        assert owner.name == "Carmen Vega"

        # Verify employees
        employees = [s for s in staff_list if s.role == StaffRole.EMPLOYEE.value]
        assert len(employees) == 2

        employee_names = [e.name for e in employees]
        assert "Ana" in employee_names
        assert "Beto" in employee_names
