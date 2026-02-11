"""Eval: Customer books an appointment (happy path).

Seeds an active business, simulates a customer requesting a booking,
and asserts the appointment was created in the DB.
"""

import pytest
from sqlalchemy import select

from app.models import Appointment, AppointmentStatus
from tests.evals.conftest import simulate_message, get_tool_calls
from tests.evals.seed_helpers import seed_active_business


@pytest.mark.eval
async def test_customer_booking_happy_path(eval_db):
    """Customer sends messages to book an appointment. AI should call
    book_appointment and create a confirmed appointment in DB."""
    data = await seed_active_business(eval_db)
    org = data["org"]

    customer_phone = "+525577001001"
    business_number = org.whatsapp_phone_number_id

    # Message 1: Customer initiates
    result1, _ = await simulate_message(
        eval_db, customer_phone, business_number,
        "Hola, quiero agendar un corte de cabello para manana en la manana",
        sender_name="Test Customer",
    )
    assert result1["status"] == "success"
    assert result1["case"] == "5"  # End customer route

    # The AI may book directly or ask for confirmation.
    # Send a follow-up agreeing to whatever time was suggested.
    result2, corr2 = await simulate_message(
        eval_db, customer_phone, business_number,
        "Si, esa hora esta bien, por favor agenda la cita",
    )
    assert result2["status"] == "success"

    # Check if an appointment was created
    apt_result = await eval_db.execute(
        select(Appointment).where(
            Appointment.organization_id == org.id,
            Appointment.status.in_([
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.PENDING.value,
            ]),
        )
    )
    appointments = apt_result.scalars().all()

    # If not booked yet, send one more confirmation
    if not appointments:
        result3, corr3 = await simulate_message(
            eval_db, customer_phone, business_number,
            "Si confirmo, quiero la cita",
        )
        assert result3["status"] == "success"

        apt_result = await eval_db.execute(
            select(Appointment).where(
                Appointment.organization_id == org.id,
                Appointment.status.in_([
                    AppointmentStatus.CONFIRMED.value,
                    AppointmentStatus.PENDING.value,
                ]),
            )
        )
        appointments = apt_result.scalars().all()

    assert len(appointments) >= 1, (
        "Expected at least one appointment to be created after booking conversation"
    )
    apt = appointments[0]
    assert apt.organization_id == org.id
    assert apt.service_type_id == data["service"].id
