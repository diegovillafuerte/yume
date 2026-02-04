"""Message Router - THE CORE of Yume's value proposition.

This module routes incoming WhatsApp messages to the correct handler based on
the two-channel architecture defined in docs/PROJECT_SPEC.md.

Two-Channel Architecture:
1. YUME CENTRAL NUMBER - B2B interactions
   - Business onboarding (unknown senders)
   - Business management (staff of single business)
   - Redirect message (staff of multiple businesses)

2. BUSINESS NUMBERS - B2C + Staff interactions
   - End customer flows (booking, inquiry, etc.)
   - Staff onboarding (pre-registered staff's first message)
   - Business management (known staff)

See docs/PROJECT_SPEC.md for the full routing decision tree and state machines.
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
    EndCustomer,
    ExecutionTraceType,
    Message,
    MessageContentType,
    MessageDirection,
    MessageSenderType,
    OnboardingSession,
    OnboardingState,
    Organization,
    YumeUser,
)
from app.services import customer as customer_service
from app.services import staff as staff_service
from app.services.conversation import ConversationHandler
from app.services.customer_flows import CustomerFlowHandler
from app.services.onboarding import OnboardingHandler
from app.services.staff_onboarding import StaffOnboardingHandler
from app.services.whatsapp import WhatsAppClient

if TYPE_CHECKING:
    from app.services.execution_tracer import ExecutionTracer

logger = logging.getLogger(__name__)


# Redirect message for multi-business staff
MULTI_BUSINESS_REDIRECT_MESSAGE = """¡Hola! Veo que estás registrado en más de un negocio:

{business_list}

Para gestionar tu agenda, escribe directamente al número de WhatsApp del negocio que quieras administrar.

Si necesitas ayuda, escríbenos a soporte@yume.mx"""


class MessageRouter:
    """Routes incoming WhatsApp messages to appropriate handlers.

    Implements the 5-case routing decision tree from docs/PROJECT_SPEC.md:

    | Case | Recipient | Sender | Route |
    |------|-----------|--------|-------|
    | 1 | Yume Central | Unknown/Incomplete onboarding | Business Onboarding |
    | 2a | Yume Central | Staff of 1 business | Business Management |
    | 2b | Yume Central | Staff of 2+ businesses | Redirect Message |
    | 3 | Business Number | Pre-registered staff (first msg) | Staff Onboarding |
    | 4 | Business Number | Known staff | Business Management |
    | 5 | Business Number | Anyone else | End Customer |
    """

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
        """Route an incoming WhatsApp message using the 5-case decision tree.

        This is THE critical function that determines the entire user experience.

        Args:
            phone_number_id: WhatsApp phone number ID that received the message
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
            f"  Content: {message_content[:100]}{'...' if len(message_content) > 100 else ''}\n"
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

        # Step 2: Determine which channel received this message
        business_org = await self._find_org_by_whatsapp_phone_id(phone_number_id)

        if business_org:
            # BUSINESS NUMBER FLOW (Cases 3, 4, 5)
            return await self._route_business_number_message(
                org=business_org,
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_id=message_id,
                message_content=message_content,
                tracer=tracer,
                skip_whatsapp_send=skip_whatsapp_send,
            )
        else:
            # YUME CENTRAL NUMBER FLOW (Cases 1, 2a, 2b)
            return await self._route_central_number_message(
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_id=message_id,
                message_content=message_content,
                tracer=tracer,
                skip_whatsapp_send=skip_whatsapp_send,
            )

    async def _route_central_number_message(
        self,
        phone_number_id: str,
        sender_phone: str,
        sender_name: str | None,
        message_id: str,
        message_content: str,
        tracer: ExecutionTracer | None = None,
        skip_whatsapp_send: bool = False,
    ) -> dict[str, str]:
        """Route message received on Yume's central WhatsApp number.

        Implements Cases 1, 2a, 2b from the routing table:
        - Case 1: Unknown sender → Business Onboarding
        - Case 2a: Staff of 1 business → Business Management
        - Case 2b: Staff of 2+ businesses → Redirect Message

        Args:
            phone_number_id: Yume's central phone number ID
            sender_phone: Sender's phone number
            sender_name: Sender's WhatsApp profile name
            message_id: WhatsApp message ID
            message_content: Message text
            tracer: Optional execution tracer
            skip_whatsapp_send: If True, don't send WhatsApp response

        Returns:
            Dict with routing decision and status
        """
        # Get ALL staff registrations for this phone number
        registrations = await staff_service.get_all_staff_registrations(
            self.db, sender_phone
        )

        if len(registrations) == 0:
            # CASE 1: Unknown sender → Business Onboarding
            logger.info(
                f"\n🟠 CASE 1: BUSINESS ONBOARDING\n"
                f"   Sender {sender_phone} is not registered with any business\n"
                f"   → Routing to OnboardingHandler"
            )

            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "case": "1",
                        "route": "business_onboarding",
                        "reason": "Unknown sender - starting onboarding",
                    })

            response_text = await self._handle_business_onboarding(
                sender_phone=sender_phone,
                message_content=message_content,
                sender_name=sender_name,
                message_id=message_id,
                tracer=tracer,
            )

            if not skip_whatsapp_send:
                await self.whatsapp.send_text_message(
                    phone_number_id=phone_number_id,
                    to=sender_phone,
                    message=response_text,
                )

            await self.db.commit()
            return {
                "status": "success",
                "case": "1",
                "sender_type": "onboarding",
                "route": "business_onboarding",
                "response_text": response_text,
            }

        elif len(registrations) == 1:
            # CASE 2a: Staff of exactly 1 business → Business Management
            staff, org = registrations[0]
            logger.info(
                f"\n🔵 CASE 2a: BUSINESS MANAGEMENT (Central Number)\n"
                f"   Staff: {staff.name} at {org.name}\n"
                f"   → Routing to Business Management Handler"
            )

            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "case": "2a",
                        "route": "business_management",
                        "organization_id": str(org.id),
                        "organization_name": org.name,
                        "staff_id": str(staff.id),
                        "staff_name": staff.name,
                    })

            # Mark first message if needed
            await staff_service.mark_first_message(self.db, staff)

            response_text = await self._handle_business_management(
                org=org,
                staff=staff,
                message_content=message_content,
                sender_phone=sender_phone,
                message_id=message_id,
                tracer=tracer,
            )

            if not skip_whatsapp_send:
                await self.whatsapp.send_text_message(
                    phone_number_id=phone_number_id,
                    to=sender_phone,
                    message=response_text,
                )

            await self.db.commit()
            return {
                "status": "success",
                "case": "2a",
                "sender_type": MessageSenderType.STAFF.value,
                "organization_id": str(org.id),
                "route": "business_management",
                "response_text": response_text,
            }

        else:
            # CASE 2b: Staff of multiple businesses → Redirect Message
            business_names = [f"• {org.name}" for _, org in registrations]
            logger.info(
                f"\n🟡 CASE 2b: MULTI-BUSINESS REDIRECT\n"
                f"   Staff registered at {len(registrations)} businesses\n"
                f"   → Sending redirect message"
            )

            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "case": "2b",
                        "route": "redirect",
                        "businesses": [org.name for _, org in registrations],
                        "reason": "Staff of multiple businesses - must message directly",
                    })

            response_text = MULTI_BUSINESS_REDIRECT_MESSAGE.format(
                business_list="\n".join(business_names)
            )

            if not skip_whatsapp_send:
                await self.whatsapp.send_text_message(
                    phone_number_id=phone_number_id,
                    to=sender_phone,
                    message=response_text,
                )

            await self.db.commit()
            return {
                "status": "success",
                "case": "2b",
                "sender_type": "multi_business_staff",
                "route": "redirect",
                "businesses": [org.name for _, org in registrations],
                "response_text": response_text,
            }

    async def _route_business_number_message(
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
        """Route message received on a business's own WhatsApp number.

        Implements Cases 3, 4, 5 from the routing table:
        - Case 3: Pre-registered staff (first message) → Staff Onboarding
        - Case 4: Known staff → Business Management
        - Case 5: Anyone else → End Customer

        Args:
            org: The organization that owns this WhatsApp number
            phone_number_id: Business's phone number ID
            sender_phone: Sender's phone number
            sender_name: Sender's WhatsApp profile name
            message_id: WhatsApp message ID
            message_content: Message text
            tracer: Optional execution tracer
            skip_whatsapp_send: If True, don't send WhatsApp response

        Returns:
            Dict with routing decision and status
        """
        # Check if sender is staff of THIS specific organization
        staff = await staff_service.get_staff_by_phone(self.db, org.id, sender_phone)

        if staff and staff.is_active:
            # Staff of this business - check if first message
            if staff_service.is_first_message(staff):
                # CASE 3: Pre-registered staff first message → Staff Onboarding
                logger.info(
                    f"\n🟢 CASE 3: STAFF ONBOARDING\n"
                    f"   Pre-registered staff {staff.name} at {org.name}\n"
                    f"   First message - starting onboarding\n"
                    f"   → Routing to Staff Onboarding Handler"
                )

                if tracer:
                    with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                        step.set_input({"sender_phone": sender_phone})
                        step.set_output({
                            "case": "3",
                            "route": "staff_onboarding",
                            "organization_id": str(org.id),
                            "organization_name": org.name,
                            "staff_id": str(staff.id),
                            "staff_name": staff.name,
                        })

                # Mark first message
                await staff_service.mark_first_message(self.db, staff)

                response_text = await self._handle_staff_onboarding(
                    org=org,
                    staff=staff,
                    message_content=message_content,
                    sender_phone=sender_phone,
                    message_id=message_id,
                    tracer=tracer,
                )

                sender_type = MessageSenderType.STAFF
            else:
                # CASE 4: Known staff → Check for pending onboarding OR Business Management
                # First check if there's a pending staff onboarding session
                staff_onboarding_handler = StaffOnboardingHandler(db=self.db)
                from app.models import StaffOnboardingSession, StaffOnboardingState
                from sqlalchemy import select

                result = await self.db.execute(
                    select(StaffOnboardingSession).where(
                        StaffOnboardingSession.staff_id == staff.id,
                        StaffOnboardingSession.state != StaffOnboardingState.COMPLETED.value,
                        StaffOnboardingSession.state != StaffOnboardingState.ABANDONED.value,
                    )
                )
                pending_session = result.scalar_one_or_none()

                if pending_session:
                    # Continue staff onboarding
                    logger.info(
                        f"\n🟢 CASE 4 → STAFF ONBOARDING (Pending)\n"
                        f"   Staff: {staff.name} at {org.name}\n"
                        f"   State: {pending_session.state}\n"
                        f"   → Continuing Staff Onboarding"
                    )

                    if tracer:
                        with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                            step.set_input({"sender_phone": sender_phone})
                            step.set_output({
                                "case": "4_onboarding",
                                "route": "staff_onboarding",
                                "via": "business_whatsapp",
                                "organization_id": str(org.id),
                                "staff_id": str(staff.id),
                                "onboarding_state": pending_session.state,
                            })

                    response_text = await staff_onboarding_handler.handle_message(
                        session=pending_session,
                        staff=staff,
                        org=org,
                        message_content=message_content,
                    )

                    # If onboarding just completed, response is None - use normal handler
                    if response_text is None:
                        response_text = await self._handle_business_management(
                            org=org,
                            staff=staff,
                            message_content=message_content,
                            sender_phone=sender_phone,
                            message_id=message_id,
                            tracer=tracer,
                        )
                else:
                    # Normal business management
                    logger.info(
                        f"\n🔵 CASE 4: BUSINESS MANAGEMENT (Business Number)\n"
                        f"   Staff: {staff.name} at {org.name}\n"
                        f"   → Routing to Business Management Handler"
                    )

                    if tracer:
                        with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                            step.set_input({"sender_phone": sender_phone})
                            step.set_output({
                                "case": "4",
                                "route": "business_management",
                                "via": "business_whatsapp",
                                "organization_id": str(org.id),
                                "organization_name": org.name,
                                "staff_id": str(staff.id),
                                "staff_name": staff.name,
                            })

                    response_text = await self._handle_business_management(
                        org=org,
                        staff=staff,
                        message_content=message_content,
                        sender_phone=sender_phone,
                        message_id=message_id,
                        tracer=tracer,
                    )

                sender_type = MessageSenderType.STAFF
        else:
            # CASE 5: Not staff → End Customer
            customer = await customer_service.get_or_create_customer(
                self.db,
                org.id,
                sender_phone,
                name=sender_name,
            )
            logger.info(
                f"\n🟣 CASE 5: END CUSTOMER\n"
                f"   Customer: {customer.name or sender_phone} at {org.name}\n"
                f"   → Routing to End Customer Handler"
            )

            if tracer:
                with tracer.trace_step(ExecutionTraceType.ROUTING_DECISION) as step:
                    step.set_input({"sender_phone": sender_phone})
                    step.set_output({
                        "case": "5",
                        "route": "end_customer",
                        "organization_id": str(org.id),
                        "organization_name": org.name,
                        "customer_id": str(customer.id),
                        "customer_name": customer.name,
                    })

            response_text = await self._handle_end_customer(
                org=org,
                customer=customer,
                message_content=message_content,
                sender_phone=sender_phone,
                message_id=message_id,
                tracer=tracer,
            )

            sender_type = MessageSenderType.CUSTOMER

        # Send response using Twilio
        if not skip_whatsapp_send:
            await self.whatsapp.send_text_message(
                phone_number_id=phone_number_id,
                to=sender_phone,
                message=response_text,
            )

        await self.db.commit()

        # Determine case number for response (already computed in routing above)
        if staff and staff.is_active:
            # We marked first_message_at in the flow, so check if it was just set
            # Staff onboarding vs management is already handled - use sender_type
            case_num = "4"  # Default to business management
            # If we went through staff onboarding, sender_type is STAFF either way
        else:
            case_num = "5"

        return {
            "status": "success",
            "case": case_num,
            "sender_type": sender_type.value,
            "organization_id": str(org.id),
            "route": "business_whatsapp",
            "response_text": response_text,
        }

    # ==========================================================================
    # Handler methods for each flow
    # ==========================================================================

    async def _handle_business_onboarding(
        self,
        sender_phone: str,
        message_content: str,
        sender_name: str | None,
        message_id: str,
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle message from user in business onboarding flow (Case 1).

        Args:
            sender_phone: Sender's phone
            message_content: Message text
            sender_name: WhatsApp profile name
            message_id: Message ID
            tracer: Optional execution tracer

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

        # Check if onboarding was already completed - redirect to business management
        if session.state == OnboardingState.COMPLETED.value and session.organization_id:
            org = await self.db.get(Organization, session.organization_id)
            if org:
                staff = await staff_service.get_staff_by_phone(
                    self.db, org.id, sender_phone
                )
                if staff:
                    logger.info(
                        f"   Onboarding already complete, redirecting to business management for {org.name}"
                    )
                    return await self._handle_business_management(
                        org=org,
                        staff=staff,
                        message_content=message_content,
                        sender_phone=sender_phone,
                        message_id=message_id,
                        tracer=tracer,
                    )

        # Continue onboarding conversation
        response = await onboarding_handler.handle_message(session, message_content)

        # Check if onboarding just completed
        await self.db.refresh(session)
        if session.state == OnboardingState.COMPLETED.value:
            logger.info(f"   🎉 Onboarding completed! Organization created.")

        return response

    async def _handle_staff_onboarding(
        self,
        org: Organization,
        staff: YumeUser,
        message_content: str,
        sender_phone: str,
        message_id: str,
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle first message from pre-registered staff (Case 3).

        Implements the staff onboarding state machine from docs/PROJECT_SPEC.md:
        initiated → collecting_name → collecting_availability → showing_tutorial → completed

        Args:
            org: Organization
            staff: Pre-registered staff member
            message_content: Message text
            sender_phone: Staff phone
            message_id: Message ID
            tracer: Optional execution tracer

        Returns:
            Response text
        """
        logger.info(f"   Staff onboarding for {staff.name} at {org.name}")

        # Store the incoming message
        await self._store_message(
            organization_id=org.id,
            sender_phone=sender_phone,
            message_id=message_id,
            direction=MessageDirection.INBOUND,
            sender_type=MessageSenderType.STAFF,
            content=message_content,
        )

        # Use the staff onboarding handler
        staff_onboarding_handler = StaffOnboardingHandler(db=self.db)

        # Get or create staff onboarding session
        session = await staff_onboarding_handler.get_or_create_session(
            staff=staff,
            organization_id=org.id,
        )

        # Check if onboarding is already complete - use normal handler
        if staff_onboarding_handler.is_onboarding_complete(session):
            logger.info(f"   Staff {staff.name} already onboarded, using normal handler")
            return await self._handle_business_management(
                org=org,
                staff=staff,
                message_content=message_content,
                sender_phone=sender_phone,
                message_id=message_id,
                tracer=tracer,
            )

        # Process through staff onboarding flow
        response = await staff_onboarding_handler.handle_message(
            session=session,
            staff=staff,
            org=org,
            message_content=message_content,
        )

        # If onboarding just completed, the response is None - use normal handler
        if response is None:
            return await self._handle_business_management(
                org=org,
                staff=staff,
                message_content=message_content,
                sender_phone=sender_phone,
                message_id=message_id,
                tracer=tracer,
            )

        return response

    async def _handle_business_management(
        self,
        org: Organization,
        staff: YumeUser,
        message_content: str,
        sender_phone: str,
        message_id: str,
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle message from staff member for business management (Cases 2a, 4).

        Args:
            org: Organization
            staff: YumeUser member
            message_content: Message text
            sender_phone: Staff phone
            message_id: Message ID
            tracer: Optional execution tracer

        Returns:
            Response text
        """
        logger.info(f"   Processing business management message with AI handler")

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
            tracer=tracer,
        )

        response = await conversation_handler.handle_staff_message(
            staff=staff,
            conversation=None,  # Staff conversations don't need persistent context
            message_content=message_content,
        )

        return response

    async def _handle_end_customer(
        self,
        org: Organization,
        customer: EndCustomer,
        message_content: str,
        sender_phone: str,
        message_id: str,
        tracer: ExecutionTracer | None = None,
    ) -> str:
        """Handle message from end customer (Case 5).

        Implements the end customer flow state machines from docs/PROJECT_SPEC.md:
        - Booking flow: initiated → collecting_service → ... → confirmed
        - Modify flow: initiated → identifying_booking → ... → confirmed
        - Cancel flow: initiated → identifying_booking → ... → cancelled
        - Rating flow: prompted → collecting_rating → ... → submitted

        Args:
            org: Organization
            customer: EndCustomer
            message_content: Message text
            sender_phone: Customer phone
            message_id: Message ID
            tracer: Optional execution tracer

        Returns:
            Response text
        """
        logger.info(f"   Processing end customer message with CustomerFlowHandler")

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

        # Use CustomerFlowHandler for state-tracked customer conversations
        flow_handler = CustomerFlowHandler(
            db=self.db,
            organization=org,
        )

        response = await flow_handler.handle_message(
            customer=customer,
            conversation=conversation,
            message_content=message_content,
        )

        return response

    # ==========================================================================
    # Helper methods
    # ==========================================================================

    async def _find_org_by_whatsapp_phone_id(
        self, phone_number_id: str
    ) -> Organization | None:
        """Find organization by their WhatsApp Business phone number ID.

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

    async def _message_already_processed(self, message_id: str) -> bool:
        """Check if message was already processed (deduplication).

        Args:
            message_id: WhatsApp message ID

        Returns:
            True if message already exists in database
        """
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
        # Try to find active conversation
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.organization_id == organization_id,
                Conversation.end_customer_id == customer_id,
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
            end_customer_id=customer_id,
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
