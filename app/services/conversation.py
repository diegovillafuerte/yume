"""AI Conversation Handler - Orchestrates AI-powered conversations.

This module handles the back-and-forth between GPT and the user,
including tool execution and conversation state management.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import OpenAIClient, get_openai_client
from app.ai.prompts import build_customer_system_prompt, build_staff_system_prompt
from app.ai.tools import CUSTOMER_TOOLS, STAFF_TOOLS, ToolHandler
from app.models import (
    Conversation,
    Customer,
    Message,
    MessageDirection,
    Organization,
    ServiceType,
    Staff,
)
from app.services.ai_handler_base import ToolCallingMixin
from app.services.tracing import traced

logger = logging.getLogger(__name__)

# Maximum conversation history to include (to manage context window)
MAX_HISTORY_MESSAGES = 20


class ConversationHandler(ToolCallingMixin):
    """Handles AI-powered conversations with customers and staff."""

    def __init__(
        self,
        db: AsyncSession,
        organization: Organization,
        openai_client: OpenAIClient | None = None,
        mock_mode: bool = False,
    ):
        """Initialize conversation handler.

        Args:
            db: Database session
            organization: Current organization
            openai_client: OpenAI client (uses singleton if not provided)
            mock_mode: If True, WhatsApp messages are mocked (for simulation)
        """
        self.db = db
        self.org = organization
        self.client = openai_client or get_openai_client()
        self.tool_handler = ToolHandler(db, organization, mock_mode=mock_mode)

    @traced
    async def handle_customer_message(
        self,
        customer: Customer,
        conversation: Conversation,
        message_content: str,
    ) -> str:
        """Handle a message from a customer.

        Args:
            customer: Customer sending the message
            conversation: Current conversation
            message_content: Message text

        Returns:
            AI response text
        """
        logger.info(f"Handling customer message: {message_content[:50]}...")

        # Check if AI is configured
        if not self.client.is_configured:
            return self._get_fallback_response("customer")

        # Get services for prompt
        services = await self._get_services()

        # Get customer's previous appointments for context
        previous_appointments = await self._get_customer_appointments(customer.id)

        # Get primary location for business hours and address
        location = await self._get_primary_location()

        # Build system prompt
        system_prompt = build_customer_system_prompt(
            org=self.org,
            customer=customer,
            services=services,
            previous_appointments=previous_appointments,
            business_hours=location.business_hours if location else None,
            address=location.address if location else None,
        )

        # Get conversation history
        messages = await self._get_conversation_history(conversation.id)

        # Add current message
        messages.append({"role": "user", "content": message_content})

        # Call Claude with tools
        response_text = await self._process_with_tools(
            system_prompt=system_prompt,
            messages=messages,
            tools=CUSTOMER_TOOLS,
            customer=customer,
            staff=None,
        )

        # Store AI response in conversation context
        await self._update_conversation_context(conversation, message_content, response_text)

        return response_text

    @traced
    async def handle_staff_message(
        self,
        staff: Staff,
        conversation: Conversation | None,
        message_content: str,
    ) -> str:
        """Handle a message from a staff member.

        Args:
            staff: Staff member sending the message
            conversation: Current conversation (may be None for staff)
            message_content: Message text

        Returns:
            AI response text
        """
        logger.info(f"Handling staff message from {staff.name}: {message_content[:50]}...")

        # Check if AI is configured
        if not self.client.is_configured:
            return self._get_fallback_response("staff", staff.name)

        # Get services for prompt
        services = await self._get_services()

        # Get primary location for business hours and address
        location = await self._get_primary_location()

        # Build system prompt
        system_prompt = build_staff_system_prompt(
            org=self.org,
            staff=staff,
            services=services,
            business_hours=location.business_hours if location else None,
            address=location.address if location else None,
        )

        # For staff, we may not have a persistent conversation
        # Start with just the current message
        messages = [{"role": "user", "content": message_content}]

        # If we have a conversation, include history
        if conversation:
            history = await self._get_conversation_history(conversation.id)
            messages = history + messages

        # Call GPT with staff tools
        response_text = await self._process_with_tools(
            system_prompt=system_prompt,
            messages=messages,
            tools=STAFF_TOOLS,
            customer=None,
            staff=staff,
        )

        return response_text

    @traced
    async def _process_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        customer: Customer | None = None,
        staff: Staff | None = None,
    ) -> str:
        """Process a message with GPT, handling tool calls.

        This wraps the shared tool loop from ToolCallingMixin with
        conversation-specific tool execution (customer/staff context).

        Args:
            system_prompt: System prompt for GPT
            messages: Conversation history
            tools: Available tools
            customer: Customer context
            staff: Staff context

        Returns:
            Final response text from GPT
        """

        async def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
            """Execute tool using ToolHandler with customer/staff context."""
            return await self.tool_handler.execute_tool(
                tool_name=tool_name,
                tool_input=tool_input,
                customer=customer,
                staff=staff,
            )

        return await self._process_with_tools_generic(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            tool_executor=execute_tool,
        )

    async def _get_services(self) -> list[ServiceType]:
        """Get active services for the organization."""
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def _get_primary_location(self):
        """Get primary location for the organization."""
        from app.models import Location

        result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        return result.scalar_one_or_none()

    async def _get_customer_appointments(self, customer_id: UUID) -> list[Any]:
        """Get customer's previous appointments."""
        from app.models import Appointment

        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.end_customer_id == customer_id,
                Appointment.organization_id == self.org.id,
            )
            .order_by(Appointment.scheduled_start.desc())
            .limit(5)
        )
        return list(result.scalars().all())

    async def _get_conversation_history(self, conversation_id: UUID) -> list[dict[str, Any]]:
        """Get conversation history for GPT.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of messages in OpenAI format
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
        messages = list(reversed(result.scalars().all()))

        history = []
        for msg in messages:
            role = "user" if msg.direction == MessageDirection.INBOUND.value else "assistant"
            history.append(
                {
                    "role": role,
                    "content": msg.content,
                }
            )

        return history

    async def _update_conversation_context(
        self,
        conversation: Conversation,
        user_message: str,
        ai_response: str,
    ) -> None:
        """Update conversation context with latest exchange.

        Args:
            conversation: Conversation to update
            user_message: User's message
            ai_response: AI's response
        """
        # Update context with summary of recent exchange
        context = conversation.context or {}
        context["last_user_message"] = user_message[:200]
        context["last_ai_response"] = ai_response[:200]
        context["last_interaction_at"] = datetime.now(UTC).isoformat()

        conversation.context = context
        conversation.last_message_at = datetime.now(UTC)
        await self.db.flush()

    def _get_fallback_response(self, user_type: str, name: str | None = None) -> str:
        """Get fallback response when AI is not configured.

        Args:
            user_type: "customer" or "staff"
            name: User's name (for staff)

        Returns:
            Fallback response text
        """
        if user_type == "staff":
            return (
                f"Hola {name or 'equipo'}! 👋\n\n"
                f"Soy Parlo, tu asistente de {self.org.name}.\n\n"
                f"El sistema de IA está siendo configurado. "
                f"Pronto podrás:\n"
                f"• Ver tu agenda\n"
                f"• Bloquear tiempo\n"
                f"• Registrar walk-ins\n"
                f"• Y más...\n\n"
                f"Por favor intenta de nuevo en unos minutos."
            )
        else:
            return (
                f"¡Hola! 👋\n\n"
                f"Bienvenido a {self.org.name}. Soy el asistente virtual de {self.org.name}.\n\n"
                f"Estamos preparando todo para atenderte. "
                f"Pronto podrás:\n"
                f"• Agendar citas\n"
                f"• Ver tus próximas citas\n"
                f"• Cancelar o reagendar\n\n"
                f"Por favor intenta de nuevo en unos minutos."
            )
