"""Onboarding-specific test fixtures and mocks."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OnboardingSession,
    OnboardingState,
    Organization,
    OrganizationStatus,
    Location,
    YumeUser,
    YumeUserRole,
    ServiceType,
)

# Aliases for readability
Staff = YumeUser
StaffRole = YumeUserRole


class MockOpenAIClient:
    """Mock OpenAI client for deterministic AI responses in tests.

    Usage:
        client = MockOpenAIClient()
        client.queue_response("text", content="Hello!")
        client.queue_response("tool", tool_calls=[{"name": "save_business_info", ...}])
        response = client.create_message(...)
    """

    is_configured = True

    def __init__(self):
        self._response_queue: list[dict[str, Any]] = []

    def queue_response(
        self,
        response_type: str,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Queue a response for the next create_message call.

        Args:
            response_type: "text" or "tool"
            content: Text content for text responses
            tool_calls: List of tool calls for tool responses
        """
        self._response_queue.append({
            "type": response_type,
            "content": content,
            "tool_calls": tool_calls or [],
        })

    def create_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return queued response or default text response."""
        if self._response_queue:
            return self._response_queue.pop(0)
        # Default to simple text response
        return {"type": "text", "content": "OK", "tool_calls": []}

    def has_tool_calls(self, response: dict[str, Any]) -> bool:
        """Check if response has tool calls."""
        return bool(response.get("tool_calls"))

    def extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool calls from response."""
        return response.get("tool_calls", [])

    def extract_text_response(self, response: dict[str, Any]) -> str:
        """Extract text from response."""
        return response.get("content", "")

    def format_assistant_message_with_tool_calls(
        self, response: dict[str, Any]
    ) -> dict[str, Any]:
        """Format assistant message with tool calls."""
        return {
            "role": "assistant",
            "content": response.get("content"),
            "tool_calls": response.get("tool_calls", []),
        }

    def format_tool_result_message(
        self, tool_call_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Format tool result message."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result),
        }


@pytest.fixture
def mock_openai_client() -> MockOpenAIClient:
    """Return a mock OpenAI client."""
    return MockOpenAIClient()


@pytest.fixture
def mock_whatsapp_client() -> MagicMock:
    """Return a mock WhatsApp client."""
    client = MagicMock()
    client.send_text_message = AsyncMock(return_value={"message_id": "test_msg_id"})
    client.is_configured = True
    return client


@pytest_asyncio.fixture
async def onboarding_session_initiated(db: AsyncSession) -> OnboardingSession:
    """Create an onboarding session in INITIATED state."""
    session = OnboardingSession(
        id=uuid4(),
        phone_number="+525551234567",
        owner_name="Carlos",
        state=OnboardingState.INITIATED.value,
        collected_data={"owner_name": "Carlos"},
        conversation_context={},
    )
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def onboarding_session_collecting_services(db: AsyncSession) -> OnboardingSession:
    """Create an onboarding session in COLLECTING_SERVICES state."""
    session = OnboardingSession(
        id=uuid4(),
        phone_number="+525559876543",
        owner_name="Maria",
        state=OnboardingState.COLLECTING_SERVICES.value,
        collected_data={
            "owner_name": "Maria",
            "business_name": "Salón Bella",
            "business_type": "salon",
        },
        conversation_context={},
    )
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def onboarding_session_with_services(db: AsyncSession) -> OnboardingSession:
    """Create an onboarding session with business info and services."""
    session = OnboardingSession(
        id=uuid4(),
        phone_number="+525551112222",
        owner_name="Juan",
        state=OnboardingState.COLLECTING_SERVICES.value,
        collected_data={
            "owner_name": "Juan",
            "business_name": "Barbería Don Juan",
            "business_type": "barbershop",
            "services": [
                {"name": "Corte de cabello", "duration_minutes": 30, "price": 150},
                {"name": "Corte y barba", "duration_minutes": 45, "price": 200},
            ],
        },
        conversation_context={},
    )
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def onboarding_session_ready_for_completion(db: AsyncSession) -> OnboardingSession:
    """Create an onboarding session ready for complete_onboarding."""
    session = OnboardingSession(
        id=uuid4(),
        phone_number="+525553334444",
        owner_name="Ana",
        state=OnboardingState.COLLECTING_SERVICES.value,
        collected_data={
            "owner_name": "Ana",
            "business_name": "Spa Relajación",
            "business_type": "spa",
            "services": [
                {"name": "Masaje relajante", "duration_minutes": 60, "price": 500},
                {"name": "Facial básico", "duration_minutes": 45, "price": 350},
            ],
            "business_hours": {
                "monday": {"open": "10:00", "close": "19:00"},
                "tuesday": {"open": "10:00", "close": "19:00"},
                "wednesday": {"open": "10:00", "close": "19:00"},
                "thursday": {"open": "10:00", "close": "19:00"},
                "friday": {"open": "10:00", "close": "19:00"},
                "saturday": {"open": "10:00", "close": "17:00"},
                "sunday": {"closed": True},
            },
        },
        conversation_context={},
    )
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def onboarding_session_with_twilio_number(db: AsyncSession) -> OnboardingSession:
    """Create an onboarding session with a Twilio provisioned number."""
    session = OnboardingSession(
        id=uuid4(),
        phone_number="+525555556666",
        owner_name="Pedro",
        state=OnboardingState.COLLECTING_SERVICES.value,
        collected_data={
            "owner_name": "Pedro",
            "business_name": "Barbería Don Pedro",
            "business_type": "barbershop",
            "services": [
                {"name": "Corte clásico", "duration_minutes": 30, "price": 120},
            ],
            "twilio_provisioned_number": "+525512345678",
            "twilio_phone_number_sid": "PN123456789",
        },
        conversation_context={},
    )
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def organization_with_twilio_number(db: AsyncSession) -> Organization:
    """Create an organization with a Twilio provisioned WhatsApp number."""
    org = Organization(
        id=uuid4(),
        name="Barbería Don Pedro",
        phone_country_code="52",
        phone_number="+525555556666",
        whatsapp_phone_number_id="+525512345678",  # The actual phone number
        timezone="America/Mexico_City",
        status=OrganizationStatus.ACTIVE.value,
        settings={
            "whatsapp_provider": "twilio",
            "twilio_phone_number": "+525512345678",
            "twilio_phone_number_sid": "PN123456789",
        },
    )
    db.add(org)
    await db.flush()
    return org


@pytest_asyncio.fixture
async def organization_with_staff(
    db: AsyncSession, organization_with_twilio_number: Organization
) -> tuple[Organization, Staff, Location]:
    """Create an organization with a staff member (owner)."""
    org = organization_with_twilio_number

    location = Location(
        id=uuid4(),
        organization_id=org.id,
        name="Principal",
        address="123 Test Street",
        is_primary=True,
    )
    db.add(location)
    await db.flush()

    staff = Staff(
        id=uuid4(),
        organization_id=org.id,
        location_id=location.id,
        name="Pedro",
        phone_number="+525555556666",
        role=StaffRole.OWNER.value,
        is_active=True,
    )
    db.add(staff)
    await db.flush()

    return org, staff, location


async def verify_organization_created(
    db: AsyncSession,
    phone_number: str,
    expected_business_name: str,
    expected_whatsapp_number: str | None = None,
) -> Organization:
    """Helper to verify organization was created correctly.

    Args:
        db: Database session
        phone_number: Owner's phone number
        expected_business_name: Expected business name
        expected_whatsapp_number: Expected WhatsApp number (if Twilio provisioned)

    Returns:
        The created organization

    Raises:
        AssertionError: If verification fails
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Organization).where(Organization.phone_number == phone_number)
    )
    org = result.scalar_one_or_none()

    assert org is not None, f"Organization not found for phone {phone_number}"
    assert org.name == expected_business_name, f"Expected name '{expected_business_name}', got '{org.name}'"

    if expected_whatsapp_number:
        assert org.whatsapp_phone_number_id == expected_whatsapp_number, (
            f"Expected whatsapp_phone_number_id '{expected_whatsapp_number}', "
            f"got '{org.whatsapp_phone_number_id}'"
        )
        # Verify it's the phone number, not the SID
        assert not org.whatsapp_phone_number_id.startswith("PN"), (
            f"whatsapp_phone_number_id should be phone number, not SID: {org.whatsapp_phone_number_id}"
        )

    return org


async def verify_staff_created(
    db: AsyncSession,
    organization_id,
    phone_number: str,
    expected_name: str,
    expected_role: str = StaffRole.OWNER.value,
) -> Staff:
    """Helper to verify staff was created correctly.

    Args:
        db: Database session
        organization_id: Organization ID
        phone_number: Staff phone number
        expected_name: Expected staff name
        expected_role: Expected role (default: OWNER)

    Returns:
        The created staff member

    Raises:
        AssertionError: If verification fails
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Staff).where(
            Staff.organization_id == organization_id,
            Staff.phone_number == phone_number,
        )
    )
    staff = result.scalar_one_or_none()

    assert staff is not None, f"Staff not found for phone {phone_number}"
    assert staff.name == expected_name, f"Expected name '{expected_name}', got '{staff.name}'"
    assert staff.role == expected_role, f"Expected role '{expected_role}', got '{staff.role}'"

    return staff


async def verify_services_created(
    db: AsyncSession,
    organization_id,
    expected_count: int,
) -> list[ServiceType]:
    """Helper to verify services were created correctly.

    Args:
        db: Database session
        organization_id: Organization ID
        expected_count: Expected number of services

    Returns:
        List of created services

    Raises:
        AssertionError: If verification fails
    """
    from sqlalchemy import select

    result = await db.execute(
        select(ServiceType).where(ServiceType.organization_id == organization_id)
    )
    services = result.scalars().all()

    assert len(services) == expected_count, f"Expected {expected_count} services, got {len(services)}"

    return list(services)
