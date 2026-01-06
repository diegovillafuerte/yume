"""Message Router - THE CORE of Yume's value proposition.

This module routes incoming WhatsApp messages to the correct handler based on
whether the sender is a registered staff member or a customer.

Critical Flow:
1. Message arrives from WhatsApp (Yume's main number)
2. Check if sender is a registered staff member of any organization
   - If yes → Route to staff handler for that org
3. Check if sender has an existing organization as customer
   - If yes → Route to customer handler for that org
4. Check if sender is in onboarding process
   - If yes → Continue onboarding
5. Otherwise → Start new business onboarding

This is what enables ONE WhatsApp number to serve multiple experiences:
- Business owners onboarding
- Staff managing their schedule
- Customers booking appointments
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ConversationStatus,
    Customer,
    Message,
    MessageContentType,
    MessageDirection,
    MessageSenderType,
    OnboardingSession,
    OnboardingState,
    Organization,
    Staff,
)
from app.services import customer as customer_service
from app.services import organization as org_service
from app.services import staff as staff_service
from app.services.conversation import ConversationHandler
from app.services.onboarding import OnboardingHandler
from app.services.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes incoming WhatsApp messages to appropriate handlers."""

    def __init__(self, db: AsyncSession, whatsapp_client: WhatsAppClient):
        """Initialize message router.

        Args:
            db: Database session
            whatsapp_client: WhatsApp API client (can be in mock mode)
        """
        self.db = db
        self.whatsapp = whatsapp_client

    async def route_message(
        self,
        phone_number_id: str,
        sender_phone: str,
        message_id: str,
        message_content: str,
        sender_name: str | None = None,
    ) -> dict[str, str]:
        """Route an incoming WhatsApp message.

        This is THE critical function that determines the entire user experience.
        It handles three types of users:
        1. Staff members of existing organizations
        2. Customers of existing organizations
        3. New business owners going through onboarding

        Args:
            phone_number_id: Our WhatsApp number (Yume's main number)
            sender_phone: Sender's phone number
            message_id: WhatsApp message ID (for deduplication)
            message_content: The message text
            sender_name: Sender's name from WhatsApp profile (optional)

        Returns:
            Dict with routing decision and status
        """
        logger.info(
            f"\n{'='*80}\n"
            f"📨 INCOMING MESSAGE\n"
            f"{'='*80}\n"
            f"  Yume Number: {phone_number_id}\n"
            f"  Sender: {sender_phone} ({sender_name or 'Unknown'})\n"
            f"  Message ID: {message_id}\n"
            f"  Content: {message_content}\n"
            f"{'='*80}"
        )

        # Step 1: Check message deduplication
        if await self._message_already_processed(message_id):
            logger.warning(f"⚠️  Message {message_id} already processed - skipping")
            return {"status": "duplicate", "message_id": message_id}

        # Step 2: Check if sender is a STAFF member of any organization
        staff, org = await self._find_staff_and_org(sender_phone)

        if staff and staff.is_active and org:
            # 🎯 STAFF MESSAGE - Route to staff handler
            logger.info(
                f"\n🔵 ROUTING DECISION: STAFF\n"
                f"   Organization: {org.name}\n"
                f"   Staff Member: {staff.name} (Role: {staff.role})\n"
                f"   → Routing to StaffConversationHandler"
            )
            response_text = await self._handle_staff_message(
                org, staff, message_content, sender_phone, message_id
            )
            sender_type = MessageSenderType.STAFF

            # Send response
            await self.whatsapp.send_text_message(
                phone_number_id=phone_number_id,
                to=sender_phone,
                message=response_text,
            )

            await self.db.commit()
            return {
                "status": "success",
                "sender_type": sender_type.value,
                "organization_id": str(org.id),
                "route": "staff",
            }

        # Step 3: Check if sender is a CUSTOMER of any organization
        customer, org = await self._find_customer_and_org(sender_phone)

        if customer and org:
            # 🎯 CUSTOMER MESSAGE - Route to customer handler
            logger.info(
                f"\n🟢 ROUTING DECISION: CUSTOMER\n"
                f"   Organization: {org.name}\n"
                f"   Customer: {customer.name or 'Unknown'} (ID: {customer.id})\n"
                f"   → Routing to CustomerConversationHandler"
            )
            response_text = await self._handle_customer_message(
                org, customer, message_content, sender_phone, message_id
            )
            sender_type = MessageSenderType.CUSTOMER

            # Send response
            await self.whatsapp.send_text_message(
                phone_number_id=phone_number_id,
                to=sender_phone,
                message=response_text,
            )

            await self.db.commit()
            return {
                "status": "success",
                "sender_type": sender_type.value,
                "organization_id": str(org.id),
                "route": "customer",
            }

        # Step 4: Neither staff nor customer - check for onboarding or start new
        logger.info(
            f"\n🟠 ROUTING DECISION: ONBOARDING\n"
            f"   Sender {sender_phone} is not associated with any organization\n"
            f"   → Routing to OnboardingHandler"
        )

        response_text = await self._handle_onboarding_message(
            sender_phone, message_content, sender_name, message_id
        )

        # Send response
        await self.whatsapp.send_text_message(
            phone_number_id=phone_number_id,
            to=sender_phone,
            message=response_text,
        )

        await self.db.commit()
        return {
            "status": "success",
            "sender_type": "onboarding",
            "route": "onboarding",
        }

    async def _find_staff_and_org(
        self, phone_number: str
    ) -> tuple[Staff | None, Organization | None]:
        """Find staff member and their organization by phone number.

        Args:
            phone_number: Phone number to look up

        Returns:
            Tuple of (Staff, Organization) or (None, None)
        """
        result = await self.db.execute(
            select(Staff, Organization)
            .join(Organization, Staff.organization_id == Organization.id)
            .where(
                Staff.phone_number == phone_number,
                Staff.is_active == True,
            )
        )
        row = result.first()
        if row:
            return row[0], row[1]
        return None, None

    async def _find_customer_and_org(
        self, phone_number: str
    ) -> tuple[Customer | None, Organization | None]:
        """Find customer and their organization by phone number.

        Args:
            phone_number: Phone number to look up

        Returns:
            Tuple of (Customer, Organization) or (None, None)
        """
        result = await self.db.execute(
            select(Customer, Organization)
            .join(Organization, Customer.organization_id == Organization.id)
            .where(Customer.phone_number == phone_number)
        )
        row = result.first()
        if row:
            return row[0], row[1]
        return None, None

    async def _handle_onboarding_message(
        self,
        sender_phone: str,
        message_content: str,
        sender_name: str | None,
        message_id: str,
    ) -> str:
        """Handle message from user in onboarding flow.

        Args:
            sender_phone: Sender's phone
            message_content: Message text
            sender_name: WhatsApp profile name
            message_id: Message ID

        Returns:
            Response text
        """
        onboarding_handler = OnboardingHandler(db=self.db)

        # Get or create onboarding session
        session = await onboarding_handler.get_or_create_session(
            phone_number=sender_phone,
            sender_name=sender_name,
        )

        logger.info(f"   Onboarding session state: {session.state}")

        # Check if onboarding was just completed - redirect to staff flow
        if session.state == OnboardingState.COMPLETED.value and session.organization_id:
            # User completed onboarding, now treat them as staff
            org = await self.db.get(Organization, session.organization_id)
            if org:
                staff = await staff_service.get_staff_by_phone(
                    self.db, org.id, sender_phone
                )
                if staff:
                    logger.info(
                        f"   Onboarding complete, redirecting to staff flow for {org.name}"
                    )
                    return await self._handle_staff_message(
                        org, staff, message_content, sender_phone, message_id
                    )

        # Continue onboarding conversation
        response = await onboarding_handler.handle_message(session, message_content)

        # Check if onboarding just completed
        await self.db.refresh(session)
        if session.state == OnboardingState.COMPLETED.value:
            logger.info(f"   🎉 Onboarding completed! Organization created.")
            # The AI response already includes the completion message

        return response

    async def _handle_staff_message(
        self,
        org: Organization,
        staff: Staff,
        message_content: str,
        sender_phone: str,
        message_id: str,
    ) -> str:
        """Handle message from staff member using AI.

        Args:
            org: Organization
            staff: Staff member
            message_content: Message text
            sender_phone: Staff phone
            message_id: Message ID

        Returns:
            Response text to send back
        """
        logger.info(f"   Processing staff message with AI handler")

        # Store the incoming message
        await self._store_message(
            organization_id=org.id,
            sender_phone=sender_phone,
            message_id=message_id,
            direction=MessageDirection.INBOUND,
            sender_type=MessageSenderType.STAFF,
            content=message_content,
        )

        # Use AI conversation handler
        conversation_handler = ConversationHandler(
            db=self.db,
            organization=org,
        )

        response = await conversation_handler.handle_staff_message(
            staff=staff,
            conversation=None,  # Staff conversations don't need persistent context
            message_content=message_content,
        )

        return response

    async def _handle_customer_message(
        self,
        org: Organization,
        customer: Customer,
        message_content: str,
        sender_phone: str,
        message_id: str,
    ) -> str:
        """Handle message from customer using AI.

        Args:
            org: Organization
            customer: Customer
            message_content: Message text
            sender_phone: Customer phone
            message_id: Message ID

        Returns:
            Response text to send back
        """
        logger.info(f"   Processing customer message with AI handler")

        # Get or create conversation
        conversation = await self._get_or_create_conversation(org.id, customer.id)

        # Store the incoming message
        await self._store_message(
            organization_id=org.id,
            sender_phone=sender_phone,
            message_id=message_id,
            direction=MessageDirection.INBOUND,
            sender_type=MessageSenderType.CUSTOMER,
            content=message_content,
            conversation_id=conversation.id,
        )

        # Use AI conversation handler
        conversation_handler = ConversationHandler(
            db=self.db,
            organization=org,
        )

        response = await conversation_handler.handle_customer_message(
            customer=customer,
            conversation=conversation,
            message_content=message_content,
        )

        return response

    async def _message_already_processed(self, message_id: str) -> bool:
        """Check if message was already processed (deduplication).

        Args:
            message_id: WhatsApp message ID

        Returns:
            True if message already exists in database
        """
        from sqlalchemy import select

        result = await self.db.execute(
            select(Message).where(Message.whatsapp_message_id == message_id)
        )
        return result.scalar_one_or_none() is not None

    async def _get_or_create_conversation(
        self, organization_id: UUID, customer_id: UUID
    ) -> Conversation:
        """Get or create active conversation for customer.

        Args:
            organization_id: Organization ID
            customer_id: Customer ID

        Returns:
            Active conversation
        """
        from sqlalchemy import select

        # Try to find active conversation
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.organization_id == organization_id,
                Conversation.customer_id == customer_id,
                Conversation.status == ConversationStatus.ACTIVE.value,
            )
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            # Update last message time
            conversation.last_message_at = datetime.now(timezone.utc)
            return conversation

        # Create new conversation
        conversation = Conversation(
            organization_id=organization_id,
            customer_id=customer_id,
            status=ConversationStatus.ACTIVE.value,
            context={},
            last_message_at=datetime.now(timezone.utc),
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def _store_message(
        self,
        organization_id: UUID,
        sender_phone: str,
        message_id: str,
        direction: MessageDirection,
        sender_type: MessageSenderType,
        content: str,
        conversation_id: UUID | None = None,
    ) -> Message:
        """Store message in database.

        Args:
            organization_id: Organization ID
            sender_phone: Sender's phone
            message_id: WhatsApp message ID
            direction: Inbound or outbound
            sender_type: Customer, staff, or AI
            content: Message content
            conversation_id: Conversation ID (optional)

        Returns:
            Created message
        """
        message = Message(
            conversation_id=conversation_id,
            direction=direction.value,
            sender_type=sender_type.value,
            content_type=MessageContentType.TEXT.value,
            content=content,
            whatsapp_message_id=message_id,
        )
        self.db.add(message)
        await self.db.flush()
        return message
