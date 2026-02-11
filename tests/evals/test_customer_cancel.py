"""Eval: Customer cancels an existing appointment.

Seeds a business with a future appointment, simulates a customer
requesting cancellation, and asserts the appointment status changed.
"""

import pytest
from sqlalchemy import select

from app.models import Appointment, AppointmentStatus
from tests.evals.conftest import simulate_message
from tests.evals.seed_helpers import seed_business_with_appointments


@pytest.mark.eval
async def test_customer_cancel(eval_db):
    """Customer with a future appointment sends messages to cancel it.
    AI should call cancel_appointment and update status to cancelled."""
    data = await seed_business_with_appointments(eval_db)
    org = data["org"]
    customer = data["customer2"]  # Has the future appointment
    apt = data["future_appointment"]

    business_number = org.whatsapp_phone_number_id

    # Message 1: Customer wants to cancel
    result1, _ = await simulate_message(
        eval_db, customer.phone_number, business_number,
        "Hola, necesito cancelar mi cita",
        sender_name=customer.name,
    )
    assert result1["status"] == "success"
    assert result1["case"] == "5"

    # Message 2: Confirm cancellation
    result2, _ = await simulate_message(
        eval_db, customer.phone_number, business_number,
        "Si, cancela por favor",
    )
    assert result2["status"] == "success"

    # Check appointment status
    await eval_db.refresh(apt)
    # It may take one more message
    if apt.status != AppointmentStatus.CANCELLED.value:
        result3, _ = await simulate_message(
            eval_db, customer.phone_number, business_number,
            "Confirmo la cancelacion",
        )
        await eval_db.refresh(apt)

    assert apt.status == AppointmentStatus.CANCELLED.value, (
        f"Expected appointment to be cancelled, got status={apt.status}"
    )
