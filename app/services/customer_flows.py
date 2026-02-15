"""Customer flow handler - manages state machines for end customer conversations.

This service implements the customer flow state machines from docs/PROJECT_SPEC.md:
- Booking flow: initiated → collecting_service → collecting_datetime → ... → confirmed
- Modify flow: initiated → identifying_booking → selecting_modification → ... → confirmed
- Cancel flow: initiated → identifying_booking → confirming_cancellation → cancelled
- Rating flow: prompted → collecting_rating → collecting_feedback → submitted

The handler wraps around the existing ConversationHandler to add explicit state tracking.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import OpenAIClient, get_openai_client
from app.ai.tools import CUSTOMER_TOOLS, ToolHandler
from app.models import (
    Appointment,
    AppointmentStatus,
    Conversation,
    CustomerFlowSession,
    CustomerFlowState,
    CustomerFlowType,
    EndCustomer,
    Organization,
    ServiceType,
)
from app.services.abandoned_state import (
    DEFAULT_TIMEOUT_MINUTES as ABANDONED_TIMEOUT_MINUTES,
    resume_from_abandoned,
)
from app.services.customer_profile import (
    format_customer_context_for_ai,
    get_customer_preferences,
    lookup_cross_business_profile,
    should_reconfirm_info,
)

logger = logging.getLogger(__name__)


def build_flow_aware_system_prompt(
    org: Organization,
    customer: EndCustomer,
    services: list[ServiceType],
    flow_session: CustomerFlowSession | None,
    previous_appointments: list[Any],
    customer_preferences: dict[str, Any] | None = None,
    cross_business_info: dict[str, Any] | None = None,
    needs_name_confirmation: bool = False,
    business_hours: dict | None = None,
    address: str | None = None,
) -> str:
    """Build system prompt that's aware of current flow state and customer profile.

    Args:
        org: Organization
        customer: End customer
        services: Available services
        flow_session: Current flow session (if any)
        previous_appointments: Customer's recent appointments
        customer_preferences: Customer preferences from profile analysis
        cross_business_info: Info from other businesses
        needs_name_confirmation: Whether to ask customer to confirm their name
        business_hours: Location business hours dict
        address: Location address

    Returns:
        System prompt string
    """
    # Base prompt
    services_list = "\n".join([
        f"  - {s.name} (ID: {s.id}): ${s.price_cents / 100:.0f} MXN ({s.duration_minutes} min)"
        for s in services
    ])

    # Build customer context using profile service
    customer_context = format_customer_context_for_ai(
        customer=customer,
        preferences=customer_preferences,
        cross_business=cross_business_info,
    )

    upcoming_apts = [a for a in previous_appointments
                     if a.scheduled_start > datetime.now(timezone.utc)
                     and a.status in [AppointmentStatus.PENDING.value, AppointmentStatus.CONFIRMED.value]]

    upcoming_summary = ""
    if upcoming_apts:
        upcoming_summary = f"\n- Citas próximas: {len(upcoming_apts)} cita(s)"

    # Returning customer context
    returning_customer_note = ""
    if cross_business_info and cross_business_info.get("total_appointments", 0) > 0:
        returning_customer_note = "\n⭐ Este es un cliente que ya ha usado Parlo antes. Trátalo con familiaridad."

    # Name confirmation context
    name_note = ""
    if needs_name_confirmation and customer.name:
        name_note = f"\n📝 Confirma si su nombre sigue siendo '{customer.name}' al momento de agendar."
    elif not customer.name:
        name_note = "\n📝 Recuerda preguntar el nombre al momento de agendar la cita."

    org_tz = ZoneInfo(org.timezone) if org.timezone else ZoneInfo("America/Mexico_City")
    now_local = datetime.now(org_tz)
    today = now_local.strftime("%Y-%m-%d")
    tomorrow = (now_local + timedelta(days=1)).strftime("%Y-%m-%d")

    # Format business hours
    from app.ai.prompts import format_business_hours
    hours_str = format_business_hours(business_hours)

    base_prompt = f"""Eres Parlo, asistente virtual de {org.name}. Ayudas a clientes a agendar citas.

## Información del Negocio
- Nombre: {org.name}
{f"- Dirección: {address}" if address else ""}
- Horario de atención:
{hours_str}

## Servicios Disponibles
{services_list}

## Cliente Actual
{customer_context}{upcoming_summary}{returning_customer_note}{name_note}

## Fechas de Referencia
- Hoy: {today}
- Mañana: {tomorrow}

## Instrucciones Generales
- Habla en español mexicano natural, usa "tú"
- Sé breve y amable (máximo 3-4 oraciones)
- Precios en pesos mexicanos (MXN)
- Horarios en formato 12h (ej: 2:00 PM)
- Si tienes el ID del servicio o empleado, úsalo en las herramientas (service_id, staff_id).
"""

    # Add flow-specific instructions if in an active flow
    if flow_session and flow_session.is_active and not flow_session.is_terminal_state:
        flow_instructions = _get_flow_instructions(flow_session, customer)
        base_prompt += f"\n## Estado Actual de Conversación\n{flow_instructions}"
    else:
        # No active flow - detect intent
        base_prompt += """
## Detectar Intención
Cuando el cliente escriba, detecta su intención:
1. **Agendar cita** → Usa `check_availability` para buscar horarios
2. **Ver mis citas** → Usa `get_my_appointments`
3. **Cancelar** → Usa `get_my_appointments` primero, luego `cancel_appointment`
4. **Cambiar cita** → Usa `get_my_appointments` primero para identificar la cita
5. **Preguntas** → Responde basándote en la info del negocio

## Flujo de Reservación Recomendado
1. Si el cliente quiere agendar, pregunta qué servicio
2. Usa `check_availability` con el servicio y fechas
3. Ofrece 3-4 opciones de horario
4. Cuando elija, usa `book_appointment`
5. Si no sabemos el nombre, pregúntalo antes de confirmar
"""

    return base_prompt


def _get_flow_instructions(flow_session: CustomerFlowSession, customer: EndCustomer) -> str:
    """Get state-specific instructions for the AI.

    Args:
        flow_session: Current flow session
        customer: End customer

    Returns:
        Flow-specific instructions
    """
    flow_type = flow_session.flow_type
    state = flow_session.state
    collected = flow_session.collected_data or {}

    if flow_type == CustomerFlowType.BOOKING.value:
        return _get_booking_flow_instructions(state, collected, customer)
    elif flow_type == CustomerFlowType.MODIFY.value:
        return _get_modify_flow_instructions(state, collected)
    elif flow_type == CustomerFlowType.CANCEL.value:
        return _get_cancel_flow_instructions(state, collected)
    elif flow_type == CustomerFlowType.RATING.value:
        return _get_rating_flow_instructions(state, collected)

    return ""


def _get_booking_flow_instructions(state: str, collected: dict, customer: EndCustomer) -> str:
    """Get booking flow state-specific instructions."""

    if state == CustomerFlowState.INITIATED.value:
        return """**Flujo: RESERVACIÓN - Inicio**
El cliente quiere agendar. Pregunta qué servicio desea.
"""

    elif state == CustomerFlowState.COLLECTING_SERVICE.value:
        return f"""**Flujo: RESERVACIÓN - Seleccionar Servicio**
Esperando que el cliente elija un servicio de la lista.
Cuando lo mencione, usa `check_availability` para buscar horarios.
"""

    elif state == CustomerFlowState.COLLECTING_DATETIME.value:
        service = collected.get("service_name", "servicio")
        return f"""**Flujo: RESERVACIÓN - Seleccionar Horario**
Servicio elegido: {service}
Ya mostraste disponibilidad. Espera que el cliente elija horario.
Cuando elija, avanza a confirmar o pedir nombre si no lo tenemos.
"""

    elif state == CustomerFlowState.COLLECTING_STAFF_PREFERENCE.value:
        return f"""**Flujo: RESERVACIÓN - Preferencia de Personal**
Pregunta si tiene preferencia de con quién quiere la cita.
Si no tiene preferencia, asigna automáticamente.
"""

    elif state == CustomerFlowState.COLLECTING_PERSONAL_INFO.value:
        customer_name = customer.name
        if customer_name:
            return f"""**Flujo: RESERVACIÓN - Confirmar Nombre**
Tenemos el nombre '{customer_name}'. Confirma si es correcto.
Si confirma, procede a mostrar resumen.
"""
        else:
            return """**Flujo: RESERVACIÓN - Pedir Nombre**
No tenemos el nombre del cliente. Pregunta: "¿A qué nombre agendo la cita?"
Usa `update_customer_info` cuando lo proporcione.
"""

    elif state == CustomerFlowState.CONFIRMING_SUMMARY.value:
        service = collected.get("service_name", "servicio")
        datetime_str = collected.get("datetime", "")
        return f"""**Flujo: RESERVACIÓN - Confirmar**
Muestra resumen de la cita:
- Servicio: {service}
- Horario: {datetime_str}
Pregunta: "¿Confirmo tu cita?"
Si dice sí, usa `book_appointment`.
"""

    elif state == CustomerFlowState.CONFIRMED.value:
        return """**Flujo: RESERVACIÓN - Completado**
La cita está confirmada. Agradece al cliente y pregunta si necesita algo más.
"""

    return ""


def _get_modify_flow_instructions(state: str, collected: dict) -> str:
    """Get modify flow state-specific instructions."""

    if state == CustomerFlowState.INITIATED.value:
        return """**Flujo: MODIFICAR - Inicio**
El cliente quiere cambiar una cita. Usa `get_my_appointments` para ver sus citas.
"""

    elif state == CustomerFlowState.IDENTIFYING_BOOKING.value:
        return """**Flujo: MODIFICAR - Identificar Cita**
Muestra las citas del cliente y pregunta cuál quiere modificar.
"""

    elif state == CustomerFlowState.SELECTING_MODIFICATION.value:
        booking_id = collected.get("booking_id", "")
        return f"""**Flujo: MODIFICAR - Seleccionar Cambio**
Cita identificada: {booking_id}
Pregunta qué quiere cambiar: horario, servicio, o cancelar.
"""

    elif state == CustomerFlowState.COLLECTING_NEW_DATETIME.value:
        return """**Flujo: MODIFICAR - Nuevo Horario**
Usa `check_availability` para mostrar horarios disponibles.
Cuando elija, usa `reschedule_appointment`.
"""

    elif state == CustomerFlowState.CONFIRMING_SUMMARY.value:
        return """**Flujo: MODIFICAR - Confirmar Cambios**
Muestra el resumen de los cambios y pide confirmación.
"""

    return ""


def _get_cancel_flow_instructions(state: str, collected: dict) -> str:
    """Get cancel flow state-specific instructions."""

    if state == CustomerFlowState.INITIATED.value:
        return """**Flujo: CANCELAR - Inicio**
El cliente quiere cancelar. Usa `get_my_appointments` para ver sus citas.
"""

    elif state == CustomerFlowState.IDENTIFYING_BOOKING.value:
        return """**Flujo: CANCELAR - Identificar Cita**
Muestra las citas del cliente y pregunta cuál quiere cancelar.
"""

    elif state == CustomerFlowState.CONFIRMING_CANCELLATION.value:
        booking_summary = collected.get("booking_summary", "la cita")
        return f"""**Flujo: CANCELAR - Confirmar**
El cliente quiere cancelar: {booking_summary}
Pregunta: "¿Estás seguro que quieres cancelar esta cita?"
Si confirma, usa `cancel_appointment`.
"""

    return ""


def _get_rating_flow_instructions(state: str, collected: dict) -> str:
    """Get rating flow state-specific instructions."""

    if state == CustomerFlowState.PROMPTED.value:
        return """**Flujo: CALIFICACIÓN - Inicio**
Acabamos de enviar solicitud de calificación al cliente.
Espera su respuesta (número del 1 al 5).
"""

    elif state == CustomerFlowState.COLLECTING_RATING.value:
        return """**Flujo: CALIFICACIÓN - Esperando Número**
Espera que el cliente dé una calificación del 1 al 5.
"""

    elif state == CustomerFlowState.COLLECTING_FEEDBACK.value:
        rating = collected.get("rating", "")
        return f"""**Flujo: CALIFICACIÓN - Comentarios**
Calificación: {rating}/5
Pregunta si quiere dejar algún comentario adicional.
Si no quiere, agradece y termina.
"""

    return ""


class CustomerFlowHandler:
    """Handles customer conversation flows with explicit state tracking."""

    def __init__(
        self,
        db: AsyncSession,
        organization: Organization,
        openai_client: OpenAIClient | None = None,
        mock_mode: bool = False,
    ):
        """Initialize customer flow handler.

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

    async def handle_message(
        self,
        customer: EndCustomer,
        conversation: Conversation,
        message_content: str,
    ) -> str:
        """Handle an incoming message from a customer.

        Args:
            customer: Customer sending the message
            conversation: Current conversation
            message_content: Message text

        Returns:
            AI response text
        """
        logger.info(f"Customer flow handler: {message_content[:50]}...")

        # Check if AI is configured
        if not self.client.is_configured:
            return self._get_fallback_response()

        # Get or create flow session
        flow_session = await self._get_active_flow_session(conversation.id)
        welcome_back_prefix = None

        # Check for abandoned state and resume if needed
        if flow_session and flow_session.state == CustomerFlowState.ABANDONED.value:
            flow_session, welcome_back_prefix = await self._resume_abandoned_session(flow_session)

        # Update last message time
        if flow_session:
            flow_session.last_message_at = datetime.now(timezone.utc)
            await self.db.flush()

        # Get services for prompt
        services = await self._get_services()

        # Get customer's previous appointments
        previous_appointments = await self._get_customer_appointments(customer.id)

        # Get customer profile context for personalization
        customer_preferences = await get_customer_preferences(self.db, customer)
        cross_business_info = await lookup_cross_business_profile(self.db, customer.phone_number)
        needs_name_confirmation = await should_reconfirm_info(customer)

        # Get primary location for business hours and address
        location = await self._get_primary_location()

        # Build flow-aware system prompt with customer profile context
        system_prompt = build_flow_aware_system_prompt(
            org=self.org,
            customer=customer,
            services=services,
            flow_session=flow_session,
            previous_appointments=previous_appointments,
            customer_preferences=customer_preferences,
            cross_business_info=cross_business_info,
            needs_name_confirmation=needs_name_confirmation,
            business_hours=location.business_hours if location else None,
            address=location.address if location else None,
        )

        # Get conversation history
        messages = await self._get_conversation_history(conversation.id)
        messages.append({"role": "user", "content": message_content})

        # Process with AI and tools
        response_text, tool_results = await self._process_with_tools(
            system_prompt=system_prompt,
            messages=messages,
            customer=customer,
        )

        # Update flow state based on tool results
        flow_session = await self._update_flow_state(
            conversation=conversation,
            customer=customer,
            flow_session=flow_session,
            message_content=message_content,
            tool_results=tool_results,
        )

        # Prepend welcome back message if resuming from abandoned state
        if welcome_back_prefix:
            response_text = f"{welcome_back_prefix}\n\n{response_text}"

        return response_text

    async def _get_active_flow_session(
        self,
        conversation_id: UUID,
    ) -> CustomerFlowSession | None:
        """Get active flow session for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Active flow session or None
        """
        result = await self.db.execute(
            select(CustomerFlowSession).where(
                CustomerFlowSession.conversation_id == conversation_id,
                CustomerFlowSession.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def _resume_abandoned_session(
        self,
        session: CustomerFlowSession,
    ) -> tuple[CustomerFlowSession, str | None]:
        """Resume an abandoned session.

        Args:
            session: Abandoned flow session

        Returns:
            Tuple of (resumed session, welcome back message or None)
        """
        # Use centralized resume logic
        welcome_message = resume_from_abandoned(session)

        await self.db.flush()

        return session, welcome_message

    async def _update_flow_state(
        self,
        conversation: Conversation,
        customer: EndCustomer,
        flow_session: CustomerFlowSession | None,
        message_content: str,
        tool_results: list[dict[str, Any]],
    ) -> CustomerFlowSession | None:
        """Update flow state based on message and tool results.

        Args:
            conversation: Conversation
            customer: Customer
            flow_session: Current flow session (if any)
            message_content: User's message
            tool_results: Results from tool executions

        Returns:
            Updated or new flow session
        """
        # Analyze tool results to determine state transitions
        for result in tool_results:
            tool_name = result.get("tool_name", "")
            tool_output = result.get("output", {})

            # Detect booking flow start
            if tool_name == "check_availability" and "slots_by_date" in tool_output:
                # Started looking at availability - booking flow
                if not flow_session or flow_session.is_terminal_state:
                    flow_session = await self._create_flow_session(
                        conversation=conversation,
                        customer=customer,
                        flow_type=CustomerFlowType.BOOKING,
                        state=CustomerFlowState.COLLECTING_DATETIME,
                    )
                elif flow_session.flow_type == CustomerFlowType.BOOKING.value:
                    flow_session.state = CustomerFlowState.COLLECTING_DATETIME.value
                    # Store service info
                    collected = dict(flow_session.collected_data or {})
                    collected["service_name"] = tool_output.get("service", "")
                    flow_session.collected_data = collected

            # Detect booking completion
            elif tool_name == "book_appointment" and tool_output.get("success"):
                if flow_session and flow_session.flow_type == CustomerFlowType.BOOKING.value:
                    flow_session.state = CustomerFlowState.CONFIRMED.value
                    flow_session.is_active = False
                    collected = dict(flow_session.collected_data or {})
                    collected["appointment_id"] = tool_output.get("appointment_id")
                    flow_session.collected_data = collected

            # Detect cancel flow
            elif tool_name == "get_my_appointments" and "cancelar" in message_content.lower():
                if not flow_session or flow_session.is_terminal_state:
                    flow_session = await self._create_flow_session(
                        conversation=conversation,
                        customer=customer,
                        flow_type=CustomerFlowType.CANCEL,
                        state=CustomerFlowState.IDENTIFYING_BOOKING,
                    )

            # Detect cancel completion
            elif tool_name == "cancel_appointment" and tool_output.get("success"):
                if flow_session and flow_session.flow_type == CustomerFlowType.CANCEL.value:
                    flow_session.state = CustomerFlowState.CANCELLED.value
                    flow_session.is_active = False

            # Detect modify flow
            elif tool_name == "reschedule_appointment" and tool_output.get("success"):
                if flow_session and flow_session.flow_type == CustomerFlowType.MODIFY.value:
                    flow_session.state = CustomerFlowState.CONFIRMED.value
                    flow_session.is_active = False

            # Customer info update (during booking)
            elif tool_name == "update_customer_info" and tool_output.get("success"):
                if flow_session and flow_session.flow_type == CustomerFlowType.BOOKING.value:
                    if flow_session.state == CustomerFlowState.COLLECTING_PERSONAL_INFO.value:
                        flow_session.state = CustomerFlowState.CONFIRMING_SUMMARY.value

        if flow_session:
            await self.db.flush()

        return flow_session

    async def _create_flow_session(
        self,
        conversation: Conversation,
        customer: EndCustomer,
        flow_type: CustomerFlowType,
        state: CustomerFlowState,
    ) -> CustomerFlowSession:
        """Create a new flow session.

        Args:
            conversation: Conversation
            customer: Customer
            flow_type: Type of flow
            state: Initial state

        Returns:
            New flow session
        """
        session = CustomerFlowSession(
            conversation_id=conversation.id,
            end_customer_id=customer.id,
            organization_id=self.org.id,
            flow_type=flow_type.value,
            state=state.value,
            is_active=True,
            collected_data={},
            last_message_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(f"Created flow session: {flow_type.value} -> {state.value}")
        return session

    async def _process_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        customer: EndCustomer,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Process message with AI, handling tool calls.

        Args:
            system_prompt: System prompt
            messages: Conversation history
            customer: Customer context

        Returns:
            Tuple of (response text, list of tool results)
        """
        max_iterations = 5
        response = None
        all_tool_results = []

        for iteration in range(max_iterations):
            response = self.client.create_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=CUSTOMER_TOOLS,
            )

            if self.client.has_tool_calls(response):
                tool_calls = self.client.extract_tool_calls(response)
                logger.info(f"AI wants to use {len(tool_calls)} tool(s)")

                messages.append(
                    self.client.format_assistant_message_with_tool_calls(response)
                )

                for tool_call in tool_calls:
                    result = await self.tool_handler.execute_tool(
                        tool_name=tool_call["name"],
                        tool_input=tool_call["input"],
                        customer=customer,
                        staff=None,
                    )

                    # Track tool results for state updates
                    all_tool_results.append({
                        "tool_name": tool_call["name"],
                        "input": tool_call["input"],
                        "output": result,
                    })

                    messages.append(
                        self.client.format_tool_result_message(tool_call["id"], result)
                    )
            else:
                response_text = self.client.extract_text_response(response)
                return response_text, all_tool_results

        logger.warning("Hit max tool iterations")
        response_text = self.client.extract_text_response(response) if response else "Lo siento, hubo un error."
        return response_text, all_tool_results

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

    async def _get_customer_appointments(self, customer_id: UUID) -> list[Appointment]:
        """Get customer's appointments."""
        result = await self.db.execute(
            select(Appointment)
            .where(Appointment.end_customer_id == customer_id)
            .order_by(Appointment.scheduled_start.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    async def _get_conversation_history(
        self,
        conversation_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get conversation history for AI."""
        from app.models import Message, MessageDirection

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        messages = list(reversed(result.scalars().all()))

        history = []
        for msg in messages:
            role = "user" if msg.direction == MessageDirection.INBOUND.value else "assistant"
            history.append({"role": role, "content": msg.content})

        return history

    def _get_fallback_response(self) -> str:
        """Get fallback response when AI is not configured."""
        return (
            f"¡Hola! Bienvenido a {self.org.name}.\n\n"
            f"Nuestro sistema está siendo configurado. "
            f"Por favor intenta más tarde o contacta directamente al negocio."
        )


async def check_abandoned_sessions(db: AsyncSession) -> int:
    """Check for and mark abandoned flow sessions.

    This should be called periodically (e.g., via Celery task).

    Args:
        db: Database session

    Returns:
        Number of sessions marked as abandoned
    """
    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=ABANDONED_TIMEOUT_MINUTES)

    # Find active sessions that have timed out
    result = await db.execute(
        select(CustomerFlowSession).where(
            CustomerFlowSession.is_active == True,
            CustomerFlowSession.last_message_at < timeout_threshold,
            CustomerFlowSession.state.notin_([
                CustomerFlowState.CONFIRMED.value,
                CustomerFlowState.CANCELLED.value,
                CustomerFlowState.SUBMITTED.value,
                CustomerFlowState.INQUIRY_ANSWERED.value,
                CustomerFlowState.ABANDONED.value,
            ]),
        )
    )
    sessions = result.scalars().all()

    for session in sessions:
        # Save current state for resumption
        collected = dict(session.collected_data or {})
        collected["last_active_state"] = session.state
        collected["abandoned_at"] = datetime.now(timezone.utc).isoformat()
        session.collected_data = collected
        session.state = CustomerFlowState.ABANDONED.value

        logger.info(
            f"Marked flow session as abandoned: {session.id}, "
            f"last state: {collected['last_active_state']}"
        )

    if sessions:
        await db.flush()

    return len(sessions)
