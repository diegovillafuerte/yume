"""Staff onboarding service - handles staff onboarding via WhatsApp conversation.

This service manages the conversational onboarding flow when a pre-registered
staff member sends their first message to the business WhatsApp number.

Flow (see docs/PROJECT_SPEC.md):
1. Owner adds staff member (pre-registers with phone number)
2. Staff member messages business WhatsApp number
3. System detects they're staff but haven't messaged before (first_message_at is NULL)
4. Staff onboarding begins, collecting:
   - Name confirmation/update
   - Availability preferences
   - Tutorial acknowledgment
5. Staff is marked as fully onboarded (first_message_at is set)
6. Owner is notified that staff completed onboarding
"""

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import OpenAIClient, get_openai_client
from app.models import (
    Organization,
    ParloUserPermissionLevel,
    Staff,
    StaffOnboardingSession,
    StaffOnboardingState,
)
from app.services.tracing import traced
from app.services.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)


# AI Tools for staff onboarding
STAFF_ONBOARDING_TOOLS = [
    {
        "name": "confirm_name",
        "description": "Confirma o actualiza el nombre del empleado. Úsalo cuando el empleado confirme su nombre o quiera cambiarlo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del empleado (como quiere que aparezca en las citas)",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "True si el empleado confirmó que el nombre es correcto",
                },
            },
            "required": ["name", "confirmed"],
        },
    },
    {
        "name": "save_availability",
        "description": "Guarda las preferencias de disponibilidad del empleado. Úsalo cuando el empleado indique sus horarios de trabajo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schedule_type": {
                    "type": "string",
                    "enum": ["same_as_business", "custom"],
                    "description": "Si usa el mismo horario del negocio o uno personalizado",
                },
                "custom_hours": {
                    "type": "object",
                    "description": "Horarios personalizados por día (si schedule_type es 'custom')",
                    "properties": {
                        "monday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "tuesday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "wednesday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "thursday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "friday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "saturday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                        "sunday": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "off": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            "required": ["schedule_type"],
        },
    },
    {
        "name": "complete_tutorial",
        "description": "Marca el tutorial como visto y completa el onboarding. Úsalo cuando el empleado confirme que entendió cómo usar Parlo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "understood": {
                    "type": "boolean",
                    "description": "True si el empleado confirmó que entendió",
                },
            },
            "required": ["understood"],
        },
    },
]


def build_staff_onboarding_system_prompt(
    session: StaffOnboardingSession,
    staff: Staff,
    org: Organization,
    business_hours_display: str | None = None,
) -> str:
    """Build the system prompt for staff onboarding conversations.

    Args:
        session: Current onboarding session
        staff: Staff member being onboarded
        org: Organization
        business_hours_display: Formatted business hours string (optional)

    Returns:
        System prompt string
    """
    collected = session.collected_data or {}
    current_name = collected.get("name") or staff.name

    # Determine current step based on state
    state = session.state
    if state == StaffOnboardingState.INITIATED.value:
        current_step = "Paso 1: Confirmar nombre"
    elif state == StaffOnboardingState.COLLECTING_NAME.value:
        current_step = "Paso 1: Confirmar nombre"
    elif state == StaffOnboardingState.COLLECTING_AVAILABILITY.value:
        current_step = "Paso 2: Confirmar disponibilidad"
    elif state == StaffOnboardingState.SHOWING_TUTORIAL.value:
        current_step = "Paso 3: Mostrar tutorial"
    else:
        current_step = "Completado"

    return f"""Eres Parlo, una asistente de inteligencia artificial que ayuda a empleados de negocios de belleza a gestionar sus citas.

## Contexto
- Negocio: {org.name}
- Empleado: {current_name}
- Este es el PRIMER mensaje de {current_name} a Parlo
- El dueño ya lo registró, ahora completamos su configuración
{f"- Horario del negocio: {business_hours_display}" if business_hours_display else ""}

## Estado Actual
{current_step}

## Datos Recolectados
- Nombre: {collected.get("name", "No confirmado aún")}
- Disponibilidad: {collected.get("availability", "No configurada")}
- Tutorial: {"Visto" if collected.get("tutorial_viewed") else "Pendiente"}

## Flujo de Onboarding

### Paso 1: Confirmar Nombre
- Saluda amablemente y da la bienvenida a {org.name}
- Pregunta si el nombre "{staff.name}" es correcto o prefieren otro
- Usa `confirm_name` cuando confirmen o proporcionen su nombre preferido
- Ejemplo: "¡Hola {staff.name}! Soy Parlo, un asistente de WhatsApp que te ayuda a gestionar tus citas en {org.name}. Tu jefe te registró — necesito confirmar un par de cosas. ¿Tu nombre '{staff.name}' es correcto o prefieres que te llame diferente?"

### Paso 2: Disponibilidad (Simplificado)
- Pregunta si trabajan el mismo horario que el negocio o tienen horario especial
- Usa `save_availability` con schedule_type="same_as_business" si usan horario del negocio
- Si tienen horario especial, pregunta qué días trabajan y en qué horario
- {('Ejemplo: "El horario de ' + org.name + " es: " + business_hours_display + '. ¿Trabajas ese mismo horario o tienes uno diferente?"') if business_hours_display else ('Ejemplo: "¿Trabajas el mismo horario que ' + org.name + ' o tienes un horario diferente?"')}

### Paso 3: Tutorial Rápido
- Explica brevemente qué pueden hacer con Parlo:
  - "Ver tu agenda del día" → les muestras sus citas
  - "Bloquear horarios" → para cuando no estén disponibles
  - "Registrar clientes que llegan sin cita" → walk-ins
- Pregunta si tienen dudas
- Usa `complete_tutorial` cuando confirmen que entendieron
- Ejemplo: "Con Parlo puedes:\n• Ver tu agenda — escribe '¿qué tengo hoy?'\n• Bloquear horarios cuando no estés\n• Registrar clientes que lleguen sin cita\n\n¿Todo claro?"

## Instrucciones
- Habla en español mexicano natural, usa "tú"
- Sé breve y amable, máximo 3-4 oraciones por mensaje
- Si el empleado tiene prisa, puedes simplificar el flujo
- Si dicen "ok", "sí", "listo" → avanza al siguiente paso
- Si completan el tutorial → notifica que ya pueden usar Parlo normalmente

## ⚠️ CRÍTICO
- SIEMPRE usa las herramientas cuando el usuario responda
- No te quedes esperando respuestas perfectas
- "Sí", "ok", "listo", "va" son confirmaciones válidas
"""


class StaffOnboardingHandler:
    """Handles staff onboarding conversations."""

    def __init__(
        self,
        db: AsyncSession,
        openai_client: OpenAIClient | None = None,
    ):
        """Initialize staff onboarding handler.

        Args:
            db: Database session
            openai_client: OpenAI client (uses singleton if not provided)
        """
        self.db = db
        self.client = openai_client or get_openai_client()

    async def get_or_create_session(
        self,
        staff: Staff,
        organization_id,
    ) -> StaffOnboardingSession:
        """Get existing or create new staff onboarding session.

        Args:
            staff: Staff member
            organization_id: Organization ID

        Returns:
            Staff onboarding session
        """
        # Check for existing session
        result = await self.db.execute(
            select(StaffOnboardingSession).where(
                StaffOnboardingSession.staff_id == staff.id,
                StaffOnboardingSession.organization_id == organization_id,
            )
        )
        session = result.scalar_one_or_none()

        if session:
            return session

        # Create new session
        session = StaffOnboardingSession(
            staff_id=staff.id,
            organization_id=organization_id,
            state=StaffOnboardingState.INITIATED.value,
            collected_data={},
            conversation_context={},
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(f"Created staff onboarding session for {staff.name} (ID: {staff.id})")
        return session

    @traced
    async def handle_message(
        self,
        session: StaffOnboardingSession,
        staff: Staff,
        org: Organization,
        message_content: str,
    ) -> str:
        """Handle an incoming message during staff onboarding.

        Args:
            session: Current onboarding session
            staff: Staff member
            org: Organization
            message_content: User's message

        Returns:
            AI response text
        """
        logger.info(
            f"Staff onboarding message from {staff.name} ({staff.phone_number}): "
            f"{message_content[:50]}..."
        )

        # Check if onboarding is already complete
        if session.state == StaffOnboardingState.COMPLETED.value:
            logger.info(f"Staff {staff.name} already completed onboarding, skipping")
            return None  # Caller should use normal staff handler

        # Check if AI is configured
        if not self.client.is_configured:
            return self._get_fallback_response(staff, org)

        # Load business hours for the prompt
        business_hours_display = None
        try:
            from app.ai.prompts import format_business_hours
            from app.models import Location

            loc_result = await self.db.execute(
                select(Location).where(
                    Location.organization_id == org.id,
                    Location.is_primary == True,
                )
            )
            location = loc_result.scalar_one_or_none()
            if location and location.business_hours:
                business_hours_display = format_business_hours(location.business_hours)
        except Exception:
            pass  # Non-critical, continue without hours

        # Build system prompt
        system_prompt = build_staff_onboarding_system_prompt(
            session, staff, org, business_hours_display=business_hours_display
        )

        # Get conversation history from context
        history = session.conversation_context.get("messages", [])

        # Add current message
        history.append({"role": "user", "content": message_content})

        # Process with AI and tools
        response_text = await self._process_with_tools(session, staff, org, system_prompt, history)

        # Update conversation history (keep last 10 messages - staff onboarding is short)
        history.append({"role": "assistant", "content": response_text})
        context = session.conversation_context or {}
        context["messages"] = history[-10:]
        session.conversation_context = context

        await self.db.flush()

        return response_text

    async def _process_with_tools(
        self,
        session: StaffOnboardingSession,
        staff: Staff,
        org: Organization,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Process message with AI, handling tool calls.

        Args:
            session: Staff onboarding session
            staff: Staff member
            org: Organization
            system_prompt: System prompt
            messages: Conversation history

        Returns:
            Final response text
        """
        max_iterations = 5

        for _iteration in range(max_iterations):
            response = self.client.create_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=STAFF_ONBOARDING_TOOLS,
            )

            if self.client.has_tool_calls(response):
                tool_calls = self.client.extract_tool_calls(response)
                logger.info(f"Staff onboarding AI wants to use {len(tool_calls)} tool(s)")

                # Add assistant message with tool calls
                messages.append(self.client.format_assistant_message_with_tool_calls(response))

                # Execute each tool
                for tool_call in tool_calls:
                    result = await self._execute_tool(
                        session,
                        staff,
                        org,
                        tool_call["name"],
                        tool_call["input"],
                    )
                    messages.append(self.client.format_tool_result_message(tool_call["id"], result))
            else:
                # Final response
                return self.client.extract_text_response(response)

        logger.warning("Hit max iterations in staff onboarding")
        return (
            self.client.extract_text_response(response)
            if response
            else "Disculpa, tuve un problema procesando tu solicitud. ¿Puedes intentar de nuevo?"
        )

    async def _execute_tool(
        self,
        session: StaffOnboardingSession,
        staff: Staff,
        org: Organization,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a staff onboarding tool.

        Args:
            session: Staff onboarding session
            staff: Staff member
            org: Organization
            tool_name: Tool to execute
            tool_input: Tool parameters

        Returns:
            Tool result
        """
        start_time = time.time()

        logger.info(
            f"\n{'=' * 60}\n"
            f"🔧 STAFF ONBOARDING TOOL EXECUTION\n"
            f"{'=' * 60}\n"
            f"   Staff: {staff.name} ({staff.phone_number})\n"
            f"   State: {session.state}\n"
            f"   Tool: {tool_name}\n"
            f"   Input: {tool_input}\n"
            f"{'=' * 60}"
        )

        collected = dict(session.collected_data or {})

        if tool_name == "confirm_name":
            name = tool_input.get("name")
            confirmed = tool_input.get("confirmed", False)

            if confirmed and name:
                collected["name"] = name
                # Also update the staff record
                staff.name = name
                session.collected_data = collected
                session.state = StaffOnboardingState.COLLECTING_AVAILABILITY.value
                await self.db.flush()

                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"   ✅ confirm_name: {name} ({elapsed_ms:.0f}ms)")

                return {
                    "success": True,
                    "message": f"Nombre confirmado: {name}",
                    "name": name,
                    "next_step": "collecting_availability",
                }
            else:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"   ⚠️ confirm_name: Not confirmed ({elapsed_ms:.0f}ms)")
                return {"success": False, "message": "Nombre no confirmado"}

        elif tool_name == "save_availability":
            schedule_type = tool_input.get("schedule_type", "same_as_business")
            custom_hours = tool_input.get("custom_hours")

            collected["availability"] = {
                "type": schedule_type,
                "custom_hours": custom_hours,
            }
            session.collected_data = collected
            session.state = StaffOnboardingState.SHOWING_TUTORIAL.value
            await self.db.flush()

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"   ✅ save_availability: {schedule_type} ({elapsed_ms:.0f}ms)")

            return {
                "success": True,
                "message": f"Disponibilidad guardada: {schedule_type}",
                "schedule_type": schedule_type,
                "next_step": "showing_tutorial",
            }

        elif tool_name == "complete_tutorial":
            understood = tool_input.get("understood", False)

            if understood:
                collected["tutorial_viewed"] = True
                session.collected_data = collected
                session.state = StaffOnboardingState.COMPLETED.value
                await self.db.flush()

                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"\n{'🎉' * 20}\n"
                    f"   STAFF ONBOARDING COMPLETED!\n"
                    f"   Staff: {staff.name}\n"
                    f"   Org: {org.name}\n"
                    f"   Duration: {elapsed_ms:.0f}ms\n"
                    f"{'🎉' * 20}"
                )

                # Notify owner that staff completed onboarding
                await self._notify_owner_staff_onboarded(org, staff)

                return {
                    "success": True,
                    "message": "Onboarding completado",
                    "staff_name": staff.name,
                    "completed": True,
                }
            else:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"   ⚠️ complete_tutorial: Not understood ({elapsed_ms:.0f}ms)")
                return {"success": False, "message": "El empleado tiene dudas"}

        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning(f"   ⚠️ Unknown tool: {tool_name} ({elapsed_ms:.0f}ms)")
        return {"error": f"Unknown tool: {tool_name}"}

    def _get_fallback_response(self, staff: Staff, org: Organization) -> str:
        """Get fallback response when AI is not configured.

        Args:
            staff: Staff member
            org: Organization

        Returns:
            Fallback message
        """
        return (
            f"¡Hola {staff.name}! 👋\n\n"
            f"Bienvenido/a a {org.name} en Parlo.\n\n"
            f"Ahora puedes:\n"
            f"• Ver tu agenda del día\n"
            f"• Bloquear horarios\n"
            f"• Registrar clientes que lleguen sin cita\n\n"
            f"¿En qué te puedo ayudar?"
        )

    def is_onboarding_complete(self, session: StaffOnboardingSession) -> bool:
        """Check if staff onboarding is complete.

        Args:
            session: Staff onboarding session

        Returns:
            True if onboarding is complete
        """
        return session.state == StaffOnboardingState.COMPLETED.value

    async def _notify_owner_staff_onboarded(
        self,
        org: Organization,
        staff: Staff,
    ) -> None:
        """Notify the organization owner(s) that a staff member completed onboarding.

        Args:
            org: Organization
            staff: Staff member who completed onboarding
        """
        # Find owner(s) of the organization
        result = await self.db.execute(
            select(Staff).where(
                Staff.organization_id == org.id,
                Staff.permission_level == ParloUserPermissionLevel.OWNER.value,
                Staff.is_active == True,
            )
        )
        owners = result.scalars().all()

        if not owners:
            logger.warning(f"No owners found for org {org.name} (ID: {org.id})")
            return

        # Build notification message
        message = (
            f"🎉 ¡{staff.name} ya está listo para usar Parlo!\n\n"
            f"Tu empleado completó su configuración y ahora puede:\n"
            f"• Ver su agenda\n"
            f"• Bloquear horarios\n"
            f"• Registrar clientes sin cita\n\n"
            f"Ya puede gestionar su agenda por WhatsApp."
        )

        # Send notification to each owner
        from app.services.whatsapp import resolve_whatsapp_sender

        whatsapp = WhatsAppClient()
        try:
            for owner in owners:
                if owner.phone_number:
                    logger.info(
                        f"Notifying owner {owner.name} ({owner.phone_number}) about {staff.name}'s onboarding"
                    )
                    try:
                        from_number = resolve_whatsapp_sender(org) or org.whatsapp_phone_number_id
                        await whatsapp.send_text_message(
                            phone_number_id=org.whatsapp_phone_number_id or "",
                            to=owner.phone_number,
                            message=message,
                            from_number=from_number,
                        )
                        logger.info(f"✅ Owner notification sent to {owner.name}")
                    except Exception as e:
                        logger.error(f"Failed to notify owner {owner.name}: {e}")
        finally:
            await whatsapp.close()
