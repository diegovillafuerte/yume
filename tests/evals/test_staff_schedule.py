"""Eval: Staff member checks their schedule.

Seeds a business with appointments, simulates staff asking for schedule,
asserts correct routing and tool usage.
"""

import pytest

from tests.evals.conftest import simulate_message, get_tool_calls
from tests.evals.seed_helpers import seed_business_with_appointments


@pytest.mark.eval
async def test_staff_checks_schedule(eval_db):
    """Staff messages business number asking for their schedule.
    Should route as Case 4 (business management)."""
    data = await seed_business_with_appointments(eval_db)
    org = data["org"]
    staff = data["staff"]

    business_number = org.whatsapp_phone_number_id

    result, corr_id = await simulate_message(
        eval_db, staff.phone_number, business_number,
        "Hola, como esta mi agenda de hoy?",
    )

    assert result["status"] == "success"
    assert result["case"] == "4"
    assert result["sender_type"] == "staff"

    # Response should contain schedule information
    response_text = result.get("response_text", "")
    assert response_text, "Expected a non-empty response about the schedule"
