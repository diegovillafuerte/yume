"""Test utility to simulate WhatsApp webhook calls.

This script helps you test the message router locally without needing
actual WhatsApp credentials or ngrok.

Usage:
    # Test webhook verification (GET request)
    python scripts/test_webhook.py --verify

    # Test message webhook (POST request)
    python scripts/test_webhook.py --customer "Hola, quiero una cita"
    python scripts/test_webhook.py --staff "Qué tengo hoy?"
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Load settings to get verify token
from app.config import get_settings

settings = get_settings()


async def send_test_webhook(
    message: str,
    phone_number_id: str = "test_phone_123",
    sender_phone: str = "525587654321",
    sender_name: str = "Test User",
):
    """Send a test webhook to the local server.

    Args:
        message: Message content to send
        phone_number_id: Our WhatsApp number ID
        sender_phone: Sender's phone number
        sender_name: Sender's name
    """
    # Meta's webhook payload format
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_number_id,
                                "display_phone_number": "+525512345678",
                            },
                            "contacts": [
                                {
                                    "wa_id": sender_phone,
                                    "profile": {"name": sender_name},
                                }
                            ],
                            "messages": [
                                {
                                    "from": sender_phone,
                                    "id": f"wamid_test_{asyncio.get_event_loop().time()}",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": message},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/webhooks/whatsapp",
                json=webhook_payload,
                timeout=30.0,
            )
            response.raise_for_status()
            print(f"✅ Webhook sent successfully")
            print(f"Response: {response.json()}")
        except httpx.HTTPError as e:
            print(f"❌ Error: {e}")
            if hasattr(e, "response"):
                print(f"Response: {e.response.text}")


async def test_webhook_verification():
    """Test webhook verification (GET request).

    This simulates what Meta does when you register your webhook URL.
    """
    print("\n" + "=" * 80)
    print("🔍 Testing WEBHOOK VERIFICATION (GET)")
    print("=" * 80)

    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.meta_webhook_verify_token,
        "hub.challenge": "test_challenge_response_123",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/v1/webhooks/whatsapp",
                params=params,
                timeout=10.0,
            )

            if response.status_code == 200 and response.text == "test_challenge_response_123":
                print(f"✅ Webhook verification PASSED")
                print(f"   Challenge echoed back: {response.text}")
            else:
                print(f"❌ Webhook verification FAILED")
                print(f"   Status: {response.status_code}")
                print(f"   Expected: test_challenge_response_123")
                print(f"   Got: {response.text}")

        except httpx.HTTPError as e:
            print(f"❌ Error: {e}")
            if hasattr(e, "response"):
                print(f"Response: {e.response.text}")


async def test_customer_message():
    """Test a message from a customer."""
    print("\n" + "=" * 80)
    print("🟢 Testing CUSTOMER message")
    print("=" * 80)

    await send_test_webhook(
        message="Hola, quiero una cita para un corte de cabello",
        sender_phone="525587654321",  # Not registered as staff
        sender_name="Juan Pérez",
    )


async def test_staff_message():
    """Test a message from a staff member.

    NOTE: You need to have a staff member registered with this phone number
    in the database for this to route correctly!
    """
    print("\n" + "=" * 80)
    print("🔵 Testing STAFF message")
    print("=" * 80)

    await send_test_webhook(
        message="Qué tengo hoy?",
        sender_phone="525512345678",  # This should be registered as staff
        sender_name="Pedro González",
    )


async def main():
    """Run test scenarios."""
    import argparse

    parser = argparse.ArgumentParser(description="Test WhatsApp webhook locally")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Test webhook verification (GET request)",
    )
    parser.add_argument(
        "--customer",
        type=str,
        help="Send a customer message with the given text",
    )
    parser.add_argument(
        "--staff",
        type=str,
        help="Send a staff message with the given text",
    )
    parser.add_argument(
        "--phone",
        type=str,
        default="525587654321",
        help="Sender phone number (default: 525587654321)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Test User",
        help="Sender name (default: Test User)",
    )

    args = parser.parse_args()

    if args.verify:
        await test_webhook_verification()
    elif args.customer:
        await send_test_webhook(
            message=args.customer,
            sender_phone=args.phone,
            sender_name=args.name,
        )
    elif args.staff:
        await send_test_webhook(
            message=args.staff,
            sender_phone=args.phone,
            sender_name=args.name,
        )
    else:
        # Run both tests
        await test_customer_message()
        await asyncio.sleep(1)
        await test_staff_message()


if __name__ == "__main__":
    asyncio.run(main())
