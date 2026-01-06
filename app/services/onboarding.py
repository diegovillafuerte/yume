"""Onboarding service - handles business registration via WhatsApp conversation.

This service manages the conversational onboarding flow where a business owner
can set up their Yume account by chatting with the AI assistant.

Flow:
1. User texts Yume's main number
2. System detects they're not associated with any organization
3. Onboarding flow begins, collecting:
   - Business name and type
   - Owner name (if not from WhatsApp profile)
   - Services offered (name, duration, price)
   - Business hours
4. Organization, Location, Staff (owner), and Services are created
5. User is redirected to normal staff flow
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import OpenAIClient, get_openai_client
from app.models import (
    Location,
    OnboardingSession,
    OnboardingState,
    Organization,
    OrganizationStatus,
    ServiceType,
    Spot,
    Staff,
    StaffRole,
)

logger = logging.getLogger(__name__)


# Default business hours for Mexican businesses
DEFAULT_BUSINESS_HOURS = {
    "monday": {"open": "09:00", "close": "19:00"},
    "tuesday": {"open": "09:00", "close": "19:00"},
    "wednesday": {"open": "09:00", "close": "19:00"},
    "thursday": {"open": "09:00", "close": "19:00"},
    "friday": {"open": "09:00", "close": "19:00"},
    "saturday": {"open": "09:00", "close": "17:00"},
    "sunday": {"closed": True},
}


# AI Tools for onboarding
ONBOARDING_TOOLS = [
    {
        "name": "save_business_info",
        "description": "Guarda la información básica del negocio cuando el usuario la proporciona.",
        "input_schema": {
            "type": "object",
            "properties": {
                "business_name": {
                    "type": "string",
                    "description": "Nombre del negocio (ej: 'Barbería Don Carlos', 'Salón Bella')",
                },
                "business_type": {
                    "type": "string",
                    "enum": ["salon", "barbershop", "spa", "nails", "other"],
                    "description": "Tipo de negocio",
                },
                "owner_name": {
                    "type": "string",
                    "description": "Nombre del dueño",
                },
            },
            "required": ["business_name", "business_type", "owner_name"],
        },
    },
    {
        "name": "add_service",
        "description": "Agrega un servicio que ofrece el negocio. Llama esta herramienta por cada servicio que el usuario mencione.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del servicio (ej: 'Corte de cabello', 'Manicure')",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duración en minutos (ej: 30, 45, 60)",
                },
                "price": {
                    "type": "number",
                    "description": "Precio en pesos mexicanos (ej: 150, 200, 500)",
                },
            },
            "required": ["name", "duration_minutes", "price"],
        },
    },
    {
        "name": "save_business_hours",
        "description": "Guarda el horario de atención del negocio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "tuesday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "wednesday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "thursday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "friday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "saturday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
                "sunday": {"type": "object", "properties": {"open": {"type": "string"}, "close": {"type": "string"}, "closed": {"type": "boolean"}}},
            },
        },
    },
    {
        "name": "complete_onboarding",
        "description": "Finaliza el proceso de registro cuando ya tienes toda la información necesaria (nombre del negocio, al menos un servicio). Llama esta herramienta solo cuando el usuario confirme que está listo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmed": {
                    "type": "boolean",
                    "description": "True si el usuario confirmó que los datos son correctos",
                },
            },
            "required": ["confirmed"],
        },
    },
]


def build_onboarding_system_prompt(session: OnboardingSession) -> str:
    """Build the system prompt for onboarding conversations.

    Args:
        session: Current onboarding session

    Returns:
        System prompt string
    """
    collected = session.collected_data or {}
    services = collected.get("services", [])

    # Build current progress summary
    progress_parts = []
    if collected.get("business_name"):
        progress_parts.append(f"- Nombre del negocio: {collected['business_name']}")
    if collected.get("business_type"):
        progress_parts.append(f"- Tipo: {collected['business_type']}")
    if collected.get("owner_name"):
        progress_parts.append(f"- Dueño: {collected['owner_name']}")
    if services:
        services_str = ", ".join([f"{s['name']} (${s['price']})" for s in services])
        progress_parts.append(f"- Servicios: {services_str}")

    progress = "\n".join(progress_parts) if progress_parts else "Ninguna información recolectada aún."

    # Determine what's missing
    missing = []
    if not collected.get("business_name"):
        missing.append("nombre del negocio")
    if not collected.get("owner_name"):
        missing.append("nombre del dueño")
    if not services:
        missing.append("servicios que ofrece (nombre, duración, precio)")

    missing_str = ", ".join(missing) if missing else "Todo listo"

    return f"""Eres Yume, una asistente de inteligencia artificial que ayuda a negocios de belleza en México a configurar su sistema de citas por WhatsApp.

## Tu objetivo
Guiar al dueño del negocio para registrar su negocio en Yume de forma conversacional, amigable y eficiente.

## Información ya recolectada
{progress}

## Información que falta
{missing_str}

## Flujo de la conversación
1. Si es la primera interacción, preséntate brevemente y explica que Yume les ayudará a agendar citas automáticamente por WhatsApp.
2. Pregunta por el nombre del negocio y el nombre del dueño.
3. Pregunta qué servicios ofrecen. Por cada servicio necesitas: nombre, duración aproximada y precio.
4. Una vez que tengas al menos un servicio, puedes preguntar si quieren agregar más o si están listos.
5. Cuando tengan toda la información básica, muestra un resumen y pregunta si es correcto.
6. Si confirman, usa la herramienta complete_onboarding.

## Instrucciones importantes
- Habla en español mexicano natural, usa "tú" no "usted".
- Sé concisa pero amable. No escribas párrafos largos.
- Puedes preguntar varios datos en una sola pregunta si fluye natural.
- Cuando el usuario diga un servicio con precio y duración, usa la herramienta add_service inmediatamente.
- Si el usuario no sabe un precio exacto, sugiere precios típicos del mercado mexicano.
- Duraciones típicas: corte 30-45min, tinte 90-120min, manicure 30-45min, pedicure 45-60min.
- El horario de atención es opcional - si no lo dan, usaremos horario estándar (9am-7pm L-V, 9am-5pm Sábado).
- NO inventes información. Solo guarda lo que el usuario te diga.
- Mantén las respuestas cortas (2-4 oraciones máximo).

## Ejemplos de respuestas
- "¡Hola! Soy Yume. Te ayudo a que tus clientes puedan agendar citas por WhatsApp automáticamente. Para empezar, ¿cómo se llama tu negocio y cuál es tu nombre?"
- "Perfecto, {collected.get('business_name', 'tu negocio')}. ¿Qué servicios ofrecen? Por ejemplo: corte $150 (30 min), tinte $500 (2 hrs)."
- "Listo, agregué {services[-1]['name'] if services else 'el servicio'}. ¿Ofrecen algún otro servicio o eso es todo?"
- "Ya tengo todo. Tu negocio '{collected.get('business_name', '')}' con {len(services)} servicio(s). ¿Está correcto?"

## Restricciones
- NUNCA compartas información de otros negocios
- Si preguntan algo que no es sobre registro, amablemente redirige la conversación
- No hagas promesas sobre funcionalidades que no existen
"""


class OnboardingHandler:
    """Handles business onboarding conversations."""

    def __init__(
        self,
        db: AsyncSession,
        openai_client: OpenAIClient | None = None,
    ):
        """Initialize onboarding handler.

        Args:
            db: Database session
            openai_client: OpenAI client (uses singleton if not provided)
        """
        self.db = db
        self.client = openai_client or get_openai_client()

    async def get_or_create_session(
        self,
        phone_number: str,
        sender_name: str | None = None,
    ) -> OnboardingSession:
        """Get existing or create new onboarding session.

        Args:
            phone_number: User's phone number
            sender_name: Name from WhatsApp profile

        Returns:
            Onboarding session
        """
        result = await self.db.execute(
            select(OnboardingSession).where(
                OnboardingSession.phone_number == phone_number,
                OnboardingSession.state != OnboardingState.COMPLETED.value,
                OnboardingSession.state != OnboardingState.ABANDONED.value,
            )
        )
        session = result.scalar_one_or_none()

        if session:
            # Update owner name if we got it from WhatsApp profile
            if sender_name and not session.owner_name:
                session.owner_name = sender_name
                collected = session.collected_data or {}
                if not collected.get("owner_name"):
                    collected["owner_name"] = sender_name
                    session.collected_data = collected
            return session

        # Create new session
        session = OnboardingSession(
            phone_number=phone_number,
            owner_name=sender_name,
            state=OnboardingState.STARTED.value,
            collected_data={"owner_name": sender_name} if sender_name else {},
            conversation_context={},
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def handle_message(
        self,
        session: OnboardingSession,
        message_content: str,
    ) -> str:
        """Handle an incoming message during onboarding.

        Args:
            session: Current onboarding session
            message_content: User's message

        Returns:
            AI response text
        """
        logger.info(f"Onboarding message from {session.phone_number}: {message_content[:50]}...")

        # Check if AI is configured
        if not self.client.is_configured:
            return self._get_fallback_response(session)

        # Build system prompt
        system_prompt = build_onboarding_system_prompt(session)

        # Get conversation history from context
        history = session.conversation_context.get("messages", [])

        # Add current message
        history.append({"role": "user", "content": message_content})

        # Process with AI and tools
        response_text = await self._process_with_tools(session, system_prompt, history)

        # Update conversation history (keep last 20 messages)
        history.append({"role": "assistant", "content": response_text})
        context = session.conversation_context or {}
        context["messages"] = history[-20:]
        session.conversation_context = context

        await self.db.flush()

        return response_text

    async def _process_with_tools(
        self,
        session: OnboardingSession,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Process message with AI, handling tool calls.

        Args:
            session: Onboarding session
            system_prompt: System prompt
            messages: Conversation history

        Returns:
            Final response text
        """
        max_iterations = 5

        for iteration in range(max_iterations):
            response = self.client.create_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=ONBOARDING_TOOLS,
            )

            if self.client.has_tool_calls(response):
                tool_calls = self.client.extract_tool_calls(response)
                logger.info(f"Onboarding AI wants to use {len(tool_calls)} tool(s)")

                # Add assistant message with tool calls
                messages.append(
                    self.client.format_assistant_message_with_tool_calls(response)
                )

                # Execute each tool
                for tool_call in tool_calls:
                    result = await self._execute_tool(
                        session,
                        tool_call["name"],
                        tool_call["input"],
                    )
                    messages.append(
                        self.client.format_tool_result_message(tool_call["id"], result)
                    )
            else:
                # Final response
                return self.client.extract_text_response(response)

        logger.warning("Hit max iterations in onboarding")
        return self.client.extract_text_response(response) if response else "Lo siento, hubo un error."

    async def _execute_tool(
        self,
        session: OnboardingSession,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an onboarding tool.

        Args:
            session: Onboarding session
            tool_name: Tool to execute
            tool_input: Tool parameters

        Returns:
            Tool result
        """
        logger.info(f"Executing onboarding tool: {tool_name} with {tool_input}")

        collected = dict(session.collected_data or {})

        if tool_name == "save_business_info":
            collected["business_name"] = tool_input.get("business_name")
            collected["business_type"] = tool_input.get("business_type")
            collected["owner_name"] = tool_input.get("owner_name")
            session.collected_data = collected
            session.state = OnboardingState.COLLECTING_SERVICES.value
            await self.db.flush()
            return {"success": True, "message": "Información del negocio guardada"}

        elif tool_name == "add_service":
            services = collected.get("services", [])
            services.append({
                "name": tool_input.get("name"),
                "duration_minutes": tool_input.get("duration_minutes"),
                "price": tool_input.get("price"),
            })
            collected["services"] = services
            session.collected_data = collected
            await self.db.flush()
            return {"success": True, "message": f"Servicio '{tool_input.get('name')}' agregado", "total_services": len(services)}

        elif tool_name == "save_business_hours":
            hours = {}
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in tool_input:
                    hours[day] = tool_input[day]
            if hours:
                collected["business_hours"] = hours
                session.collected_data = collected
                await self.db.flush()
            return {"success": True, "message": "Horario guardado"}

        elif tool_name == "complete_onboarding":
            if not tool_input.get("confirmed"):
                return {"success": False, "message": "El usuario no confirmó"}

            # Verify we have minimum required data
            if not collected.get("business_name"):
                return {"success": False, "error": "Falta el nombre del negocio"}
            if not collected.get("services"):
                return {"success": False, "error": "Falta al menos un servicio"}

            # Create the organization and all related entities
            try:
                org = await self._create_organization(session)
                session.state = OnboardingState.COMPLETED.value
                session.organization_id = str(org.id)
                await self.db.flush()
                return {
                    "success": True,
                    "message": "Registro completado",
                    "organization_id": str(org.id),
                    "business_name": org.name,
                }
            except Exception as e:
                logger.error(f"Error creating organization: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        return {"error": f"Unknown tool: {tool_name}"}

    async def _create_organization(self, session: OnboardingSession) -> Organization:
        """Create organization and all related entities from session data.

        Args:
            session: Completed onboarding session

        Returns:
            Created organization
        """
        collected = session.collected_data
        logger.info(f"Creating organization from onboarding: {collected}")

        # 1. Create Organization
        org = Organization(
            name=collected["business_name"],
            phone_country_code=self._extract_country_code(session.phone_number),
            phone_number=session.phone_number,
            whatsapp_phone_number_id=session.phone_number,  # Use phone as ID for now
            timezone="America/Mexico_City",
            status=OrganizationStatus.ACTIVE.value,
            settings={
                "language": "es",
                "currency": "MXN",
                "business_type": collected.get("business_type", "salon"),
            },
        )
        self.db.add(org)
        await self.db.flush()
        await self.db.refresh(org)
        logger.info(f"Created organization: {org.id}")

        # 2. Create Location
        location = Location(
            organization_id=org.id,
            name="Principal",
            address=collected.get("address", ""),
            business_hours=collected.get("business_hours", DEFAULT_BUSINESS_HOURS),
            is_primary=True,
        )
        self.db.add(location)
        await self.db.flush()
        await self.db.refresh(location)
        logger.info(f"Created location: {location.id}")

        # 3. Create Services
        services = []
        for svc_data in collected.get("services", []):
            # Convert price to cents (price_cents field stores cents)
            price_cents = int(svc_data["price"] * 100)
            service = ServiceType(
                organization_id=org.id,
                name=svc_data["name"],
                duration_minutes=svc_data["duration_minutes"],
                price_cents=price_cents,
                is_active=True,
            )
            self.db.add(service)
            services.append(service)

        await self.db.flush()
        for svc in services:
            await self.db.refresh(svc)
        logger.info(f"Created {len(services)} services")

        # 4. Create default Spot
        spot = Spot(
            organization_id=org.id,
            location_id=location.id,
            name="Estación 1",
            is_active=True,
        )
        self.db.add(spot)
        await self.db.flush()
        await self.db.refresh(spot)

        # Link spot to all services
        spot.service_types.extend(services)
        logger.info(f"Created spot: {spot.id}")

        # 5. Create Staff (owner)
        owner_name = collected.get("owner_name") or session.owner_name or "Dueño"
        staff = Staff(
            organization_id=org.id,
            location_id=location.id,
            default_spot_id=spot.id,
            name=owner_name,
            phone_number=session.phone_number,
            role=StaffRole.OWNER.value,
            is_active=True,
            permissions={"can_manage_all": True},
        )
        self.db.add(staff)
        await self.db.flush()
        await self.db.refresh(staff)

        # Link staff to all services
        staff.service_types.extend(services)
        logger.info(f"Created staff (owner): {staff.id}")

        await self.db.commit()
        return org

    def _extract_country_code(self, phone: str) -> str:
        """Extract country code from phone number.

        Args:
            phone: Phone number like +521234567890

        Returns:
            Country code like "52"
        """
        if phone.startswith("+"):
            phone = phone[1:]
        # Mexican numbers
        if phone.startswith("52"):
            return "52"
        # US/Canada
        if phone.startswith("1"):
            return "1"
        return "52"  # Default to Mexico

    def _get_fallback_response(self, session: OnboardingSession) -> str:
        """Get fallback response when AI is not configured.

        Args:
            session: Current session

        Returns:
            Fallback message
        """
        return (
            "¡Hola! Soy Yume, tu asistente para agendar citas.\n\n"
            "El sistema está siendo configurado. "
            "Por favor intenta más tarde.\n\n"
            "Si necesitas ayuda urgente, contacta a soporte."
        )


async def get_onboarding_session_by_phone(
    db: AsyncSession,
    phone_number: str,
) -> OnboardingSession | None:
    """Get active onboarding session for a phone number.

    Args:
        db: Database session
        phone_number: Phone number to look up

    Returns:
        Active onboarding session or None
    """
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.phone_number == phone_number,
            OnboardingSession.state != OnboardingState.COMPLETED.value,
            OnboardingSession.state != OnboardingState.ABANDONED.value,
        )
    )
    return result.scalar_one_or_none()
