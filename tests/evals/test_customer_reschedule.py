"""Eval: Customer reschedules an existing appointment.

Seeds a business with a future appointment, simulates reschedule,
asserts the appointment time changed in DB.
"""

import pytest
from sqlalchemy import select

from app.models import Appointment, AppointmentStatus
from tests.evals.conftest import simulate_message
from tests.evals.seed_helpers import seed_business_with_appointments


@pytest.mark.eval
async def test_customer_reschedule(eval_db):
    """Customer with a future appointment requests reschedule.
    AI should call reschedule_appointment and update the appointment time."""
    data = await seed_business_with_appointments(eval_db)
    org = data["org"]
    customer = data["customer2"]  # Has the future appointment
    apt = data["future_appointment"]
    original_start = apt.start_time

    business_number = org.whatsapp_phone_number_id

    # Message 1: Customer wants to reschedule
    result1, _ = await simulate_message(
        eval_db, customer.phone_number, business_number,
        "Hola, necesito cambiar mi cita para mas tarde, como a las 3 de la tarde",
        sender_name=customer.name,
    )
    assert result1["status"] == "success"
    assert result1["case"] == "5"

    # Message 2: Confirm
    result2, _ = await simulate_message(
        eval_db, customer.phone_number, business_number,
        "Si, esa hora esta bien",
    )
    assert result2["status"] == "success"

    # Check appointment was modified
    await eval_db.refresh(apt)

    # May need another confirmation
    if apt.start_time == original_start and apt.status != AppointmentStatus.CANCELLED.value:
        result3, _ = await simulate_message(
            eval_db, customer.phone_number, business_number,
            "Si, confirmo el cambio",
        )
        await eval_db.refresh(apt)

    # The appointment should have a different start_time or a new appointment created
    # Check for any confirmed appointment with different time
    all_apts = await eval_db.execute(
        select(Appointment).where(
            Appointment.organization_id == org.id,
            Appointment.end_customer_id == customer.id,
            Appointment.status.in_([
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.PENDING.value,
            ]),
        )
    )
    confirmed = all_apts.scalars().all()

    assert len(confirmed) >= 1, "Expected at least one confirmed appointment after reschedule"

    # Either the original was modified or cancelled+new created
    times_changed = any(a.start_time != original_start for a in confirmed)
    original_cancelled = apt.status == AppointmentStatus.CANCELLED.value and len(confirmed) >= 1

    assert times_changed or original_cancelled, (
        f"Expected appointment time to change or original to be cancelled. "
        f"Original start={original_start}, current appointments: "
        f"{[(a.start_time, a.status) for a in confirmed]}"
    )
