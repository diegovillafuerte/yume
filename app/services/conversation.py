"""AI Conversation Handler - Orchestrates AI-powered conversations.

This module handles the back-and-forth between GPT and the user,
including tool execution and conversation state management.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tracing import traced
from app.ai.client import OpenAIClient, get_openai_client
from app.ai.prompts import build_customer_system_prompt, build_staff_system_prompt
from app.ai.tools import CUSTOMER_TOOLS, STAFF_TOOLS, ToolHandler
from app.models import (
    Conversation,
    ConversationStatus,
    Customer,
    ExecutionTraceType,
    Message,
    MessageContentType,
    MessageDirection,
    MessageSenderType,
    Organization,
    ServiceType,
    Staff,
)

if TYPE_CHECKING:
    from app.services.execution_tracer import ExecutionTracer

logger = logging.getLogger(__name__)

# Maximum conversation history to include (to manage context window)
MAX_HISTORY_MESSAGES = 20


class ConversationHandler:
    """Handles AI-powered conversations with customers and staff."""

    def __init__(
        self,
        db: AsyncSession,
        organization: Organization,
        openai_client: OpenAIClient | None = None,
        tracer: ExecutionTracer | None = None,
    ):
        """Initialize conversation handler.

        Args:
            db: Database session
            organization: Current organization
            openai_client: OpenAI client (uses singleton if not provided)
            tracer: Optional execution tracer for debugging
        """
        self.db = db
        self.org = organization
        self.client = openai_client or get_openai_client()
        self.tool_handler = ToolHandler(db, organization)
        self.tracer = tracer

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

        # Build system prompt
        system_prompt = build_customer_system_prompt(
            org=self.org,
            customer=customer,
            services=services,
            previous_appointments=previous_appointments,
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

        # Build system prompt
        system_prompt = build_staff_system_prompt(
            org=self.org,
            staff=staff,
            services=services,
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

        This implements the tool use loop:
        1. Send message to GPT
        2. If GPT wants to use a tool, execute it
        3. Send tool result back to GPT
        4. Repeat until GPT gives a final response

        Args:
            system_prompt: System prompt for GPT
            messages: Conversation history
            tools: Available tools
            customer: Customer context
            staff: Staff context

        Returns:
            Final response text from GPT
        """
        from app.services.execution_tracer import truncate_for_trace

        max_iterations = 5  # Prevent infinite loops
        response = None
        llm_call_num = 0

        for iteration in range(max_iterations):
            logger.debug(f"Tool loop iteration {iteration + 1}")
            llm_call_num += 1

            # Call GPT with optional tracing
            if self.tracer:
                with self.tracer.trace_step(ExecutionTraceType.LLM_CALL) as step:
                    step.set_input({
                        "system_prompt_preview": truncate_for_trace(system_prompt, 300),
                        "messages_count": len(messages),
                        "messages_preview": truncate_for_trace(messages[-2:] if len(messages) >= 2 else messages, 500),
                        "tools": [t["name"] for t in tools],
                        "llm_call_number": llm_call_num,
                    })

                    response = self.client.create_message(
                        system_prompt=system_prompt,
                        messages=messages,
                        tools=tools,
                    )

                    # Extract response info for trace
                    has_tools = self.client.has_tool_calls(response)
                    tool_calls = self.client.extract_tool_calls(response) if has_tools else []
                    text_response = self.client.extract_text_response(response) if not has_tools else None

                    step.set_output({
                        "has_tool_calls": has_tools,
                        "tool_calls": [{"name": tc["name"], "input": tc["input"]} for tc in tool_calls] if tool_calls else None,
                        "response_preview": truncate_for_trace(text_response, 300) if text_response else None,
                        "finish_reason": "tool_calls" if has_tools else "stop",
                    })

                    # Add token usage if available
                    if hasattr(response, 'usage') and response.usage:
                        step.set_metadata({
                            "model": getattr(response, 'model', 'unknown'),
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        })
            else:
                response = self.client.create_message(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                )

            # Check if GPT wants to use tools
            if self.client.has_tool_calls(response):
                tool_calls = self.client.extract_tool_calls(response)
                logger.info(f"GPT wants to use {len(tool_calls)} tool(s)")

                # Add assistant's response (with tool calls) to messages
                messages.append(
                    self.client.format_assistant_message_with_tool_calls(response)
                )

                # Execute each tool and add results as separate messages
                for tool_call in tool_calls:
                    # Execute tool with optional tracing
                    if self.tracer:
                        with self.tracer.trace_step(ExecutionTraceType.TOOL_EXECUTION) as step:
                            step.set_input({
                                "tool_name": tool_call["name"],
                                "tool_input": tool_call["input"],
                            })

                            result = await self.tool_handler.execute_tool(
                                tool_name=tool_call["name"],
                                tool_input=tool_call["input"],
                                customer=customer,
                                staff=staff,
                            )

                            step.set_output({
                                "result": truncate_for_trace(result, 500),
                            })

                            if "error" in result:
                                step.set_error(result["error"])
                    else:
                        result = await self.tool_handler.execute_tool(
                            tool_name=tool_call["name"],
                            tool_input=tool_call["input"],
                            customer=customer,
                            staff=staff,
                        )

                    # Add tool result message in OpenAI format
                    messages.append(
                        self.client.format_tool_result_message(tool_call["id"], result)
                    )

            else:
                # GPT gave a final response
                response_text = self.client.extract_text_response(response)
                logger.info(f"GPT final response: {response_text[:100]}...")

                # Trace response assembly
                if self.tracer:
                    with self.tracer.trace_step(ExecutionTraceType.RESPONSE_ASSEMBLED) as step:
                        step.set_input({"llm_iterations": llm_call_num})
                        step.set_output({
                            "response_preview": truncate_for_trace(response_text, 300),
                            "response_length": len(response_text),
                        })

                return response_text

        # If we hit max iterations, return what we have
        logger.warning("Hit max tool iterations, returning last response")
        return self.client.extract_text_response(response) if response else "Lo siento, hubo un error."

    async def _get_services(self) -> list[ServiceType]:
        """Get active services for the organization."""
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def _get_customer_appointments(self, customer_id: UUID) -> list[Any]:
        """Get customer's previous appointments."""
        from app.models import Appointment

        result = await self.db.execute(
            select(Appointment)
            .where(Appointment.customer_id == customer_id)
            .order_by(Appointment.scheduled_start.desc())
            .limit(5)
        )
        return list(result.scalars().all())

    async def _get_conversation_history(
        self, conversation_id: UUID
    ) -> list[dict[str, Any]]:
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
            history.append({
                "role": role,
                "content": msg.content,
            })

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
        context["last_interaction_at"] = datetime.now(timezone.utc).isoformat()

        conversation.context = context
        conversation.last_message_at = datetime.now(timezone.utc)
        await self.db.flush()

    def _get_fallback_response(
        self, user_type: str, name: str | None = None
    ) -> str:
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
                f"Soy Yume, tu asistente de {self.org.name}.\n\n"
                f"El sistema de IA está siendo configurado. "
                f"Pronto podrás:\n"
                f"• Ver tu agenda\n"
                f"• Bloquear tiempo\n"
                f"• Registrar walk-ins\n"
                f"• Y más...\n\n"
                f"Por favor intenta más tarde."
            )
        else:
            return (
                f"¡Hola! 👋\n\n"
                f"Bienvenido a {self.org.name}. Soy Yume, tu asistente virtual.\n\n"
                f"El sistema está siendo configurado. "
                f"Pronto podrás:\n"
                f"• Agendar citas\n"
                f"• Ver tus próximas citas\n"
                f"• Cancelar o reagendar\n\n"
                f"Por favor intenta más tarde o contacta directamente al negocio."
            )
