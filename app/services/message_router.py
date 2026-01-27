"""Message Router - THE CORE of Yume's value proposition.

This module routes incoming WhatsApp messages to the correct handler based on
whether the sender is a registered staff member or an end customer.

Critical Flow:
1. Message arrives from WhatsApp
2. Check if phone_number_id matches a business's WhatsApp number
   - If yes → Route to that org's end_customer/yume_user handler
3. Check if sender is a registered yume_user (staff) of any organization
   - If yes → Route to yume_user handler for that org
4. Otherwise → Route to onboarding (new business setup)

This enables:
- Business owners onboarding via Yume's main number
- Yume users (staff) managing their schedule via Yume's main number
- End customers booking appointments via business's own WhatsApp number
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ConversationStatus,
    ExecutionTraceType,
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

if TYPE_CHECKING:
    from app.services.execution_tracer import ExecutionTracer

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
        tracer: ExecutionTracer | None = None,
        skip_whatsapp_send: bool = False,
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
            tracer: Optional execution tracer for debugging
            skip_whatsapp_send: If True, don't send WhatsApp response (for playground)

        Returns:
            Dict with routing decision and status
        """
        logger.info(
            f"\n{'='*80}\n"
            f"📨 INCOMING MESSAGE\n"
            f"{'='*80}\n"
            f"  WhatsApp Number ID: {phone_number_id}\n"
            f"  Sender: {sender_phone} ({sender_name or 'Unknown'})\n"
            f"  Message ID: {message_id}\n"
            f"  Content: {message_content}\n"
            f"{'='*80}"
        )

        # Trace message received
        if tracer:
            with tracer.trace_step(ExecutionTraceType.MESSAGE_RECEIVED) as step:
                step.set_input({
                    "phone_number_id": phone_number_id,
                    "sender_phone": sender_phone,
                    "message_id": message_id,
                    "message_preview": message_content[:200] if message_content else "",
                    "sender_name": sender_name,
                })
                step.set_output({"status": "received"})

        # Step 1: Check message deduplication
        if await self._message_already_processed(message_id):
            logger.warning(f"⚠️  Message {message_id} already processed - skipping")
            return {"status": "duplicate", "message_id": message_id}

        # Step 2: Check if this is a BUSINESS WhatsApp number (not Yume's main number)
        business_org = await self._find_org_by_whatsapp_phone_id(phone_number_id)
        if business_org:
            # This message came to a business's own WhatsApp number
            # Route as customer message for that specific organization
            logger.info(
                f"\n🏢 ROUTING DECISION: BUSINESS WHATSAPP\n"
                f"   Organization: {business_org.name}\n"
                f"   Phone Number ID: {phone_number_id}\n"
                f"   → Routing to business-specific handler"
            )
            return await self._handle_business_whatsapp_message(
                org=business_org,
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_id=message_id,
                message_content=message_content,
                tracer=tracer,
                skip_whatsapp_send=skip_whatsapp_send,
            )

        # Step 3: Check if sender is a STAFF member of any organization
        staff, org = await self._find_staff_and_org(sender_phone)

        if staff and staff.is_active and org:
            # 🎯 STAFF MESSAGE - Route to staff handler
            logger.info(
                f"\n🔵 ROUTING DECISION: STAFF\n"
                f"   Organization: {org.name}\n"
                f"   Staff Member: {staff.name} (Role: {staff.role})\n"
                f"   → Routing to StaffConversationHandler"
            )

            # Trace routing decision
            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "route": "staff",
                        "organization_id": str(org.id),
                        "organization_name": org.name,
                        "staff_id": str(staff.id),
                        "staff_name": staff.name,
                        "staff_role": staff.role,
                    })

            response_text = await self._handle_staff_message(
                org, staff, message_content, sender_phone, message_id, tracer=tracer
            )
            sender_type = MessageSenderType.STAFF

            # Send response (skip if playground mode)
            if not skip_whatsapp_send:
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
                "response_text": response_text,
            }

        # Step 3: Not a yume_user - route to onboarding (new business or continue onboarding)
        logger.info(
            f"\n🟠 ROUTING DECISION: ONBOARDING\n"
            f"   Sender {sender_phone} is not associated with any organization\n"
            f"   → Routing to OnboardingHandler"
        )

        # Trace routing decision
        if tracer:
            with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                step.set_input({"sender_phone": sender_phone})
                step.set_output({
                    "route": "onboarding",
                    "reason": "Unknown sender - starting onboarding",
                })

        response_text = await self._handle_onboarding_message(
            sender_phone, message_content, sender_name, message_id
        )

        # Send response (skip if playground mode)
        if not skip_whatsapp_send:
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
            "response_text": response_text,
        }

    async def _find_org_by_whatsapp_phone_id(
        self, phone_number_id: str
    ) -> Organization | None:
        """Find organization by their WhatsApp Business phone number ID.

        This is used when a message arrives on a business's own WhatsApp number
        (not Yume's main number).

        Args:
            phone_number_id: Meta's phone number ID for the business

        Returns:
            Organization or None
        """
        result = await self.db.execute(
            select(Organization).where(
                Organization.whatsapp_phone_number_id == phone_number_id
            )
        )
        return result.scalar_one_or_none()

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

    async def _handle_business_whatsapp_message(
        self,
        org: Organization,
        phone_number_id: str,
        sender_phone: str,
        sender_name: str | None,
        message_id: str,
        message_content: str,
        tracer: ExecutionTracer | None = None,
        skip_whatsapp_send: bool = False,
    ) -> dict[str, str]:
        """Handle message from a business's own WhatsApp number.

        When a customer messages a business's WhatsApp number directly (not Yume's
        main number), we route them to that specific business.

        Args:
            org: The organization that owns this WhatsApp number
            phone_number_id: Meta's phone number ID
            sender_phone: Sender's phone number
            sender_name: Sender's name from WhatsApp profile
            message_id: WhatsApp message ID
            message_content: The message text
            tracer: Optional execution tracer for debugging
            skip_whatsapp_send: If True, don't send WhatsApp response

        Returns:
            Dict with routing decision and status
        """
        # Check if sender is staff of this org
        staff = await staff_service.get_staff_by_phone(self.db, org.id, sender_phone)
        if staff and staff.is_active:
            logger.info(f"   Staff member {staff.name} messaging on business WhatsApp")

            # Trace routing decision
            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "route": "staff",
                        "via": "business_whatsapp",
                        "organization_id": str(org.id),
                        "organization_name": org.name,
                        "staff_id": str(staff.id),
                        "staff_name": staff.name,
                    })

            response_text = await self._handle_staff_message(
                org, staff, message_content, sender_phone, message_id, tracer=tracer
            )
            sender_type = MessageSenderType.STAFF
        else:
            # Treat as customer - get or create customer for this org
            customer = await customer_service.get_or_create_customer(
                self.db,
                org.id,
                sender_phone,
                name=sender_name,
            )
            logger.info(f"   Customer {customer.name or sender_phone} messaging business")

            # Trace routing decision
            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "route": "customer",
                        "via": "business_whatsapp",
                        "organization_id": str(org.id),
                        "organization_name": org.name,
                        "customer_id": str(customer.id),
                        "customer_name": customer.name,
                    })

            response_text = await self._handle_customer_message(
                org, customer, message_content, sender_phone, message_id, tracer=tracer
            )
            sender_type = MessageSenderType.CUSTOMER

        # Send response using the business's own WhatsApp number (skip if playground)
        if not skip_whatsapp_send:
            await self.whatsapp.send_text_message(
                phone_number_id=phone_number_id,
                to=sender_phone,
                message=response_text,
                org_access_token=self._get_org_access_token(org),
            )

        await self.db.commit()
        return {
            "status": "success",
            "sender_type": sender_type.value,
            "organization_id": str(org.id),
            "route": "business_whatsapp",
            "response_text": response_text,
        }

    def _get_org_access_token(self, org: Organization) -> str | None:
        """Get the WhatsApp access token for an organization.

        Args:
            org: Organization

        Returns:
            Access token or None if using Yume's main number
        """
        if org.settings and isinstance(org.settings, dict):
            return org.settings.get("whatsapp_access_token")
        return None

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
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle message from staff member using AI.

        Args:
            org: Organization
            staff: Staff member
            message_content: Message text
            sender_phone: Staff phone
            message_id: Message ID
            tracer: Optional execution tracer for debugging

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

        # Use AI conversation handler with tracer
        conversation_handler = ConversationHandler(
            db=self.db,
            organization=org,
            tracer=tracer,
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
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle message from customer using AI.

        Args:
            org: Organization
            customer: Customer
            message_content: Message text
            sender_phone: Customer phone
            message_id: Message ID
            tracer: Optional execution tracer for debugging

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

        # Use AI conversation handler with tracer
        conversation_handler = ConversationHandler(
            db=self.db,
            organization=org,
            tracer=tracer,
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
