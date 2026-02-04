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

import logging
import secrets
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
    YumeUserPermissionLevel,
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


from app.config import get_settings
from app.services.twilio_provisioning import provision_number_for_business

# Get frontend URL from config
_settings = get_settings()

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
                "address": {
                    "type": "string",
                    "description": "Dirección del negocio (opcional)",
                },
                "city": {
                    "type": "string",
                    "description": "Ciudad (opcional)",
                },
            },
            "required": ["business_name", "business_type", "owner_name"],
        },
    },
    {
        "name": "add_service",
        "description": "Agrega un servicio que ofrece el negocio. Llama esta herramienta por cada servicio que el usuario mencione. Después de llamar esta herramienta, SIEMPRE muestra al usuario su menú actualizado.",
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
        "name": "get_current_menu",
        "description": "Obtiene el menú de servicios actual para mostrarlo al usuario. Úsalo cuando necesites mostrar el menú completo.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "add_staff_member",
        "description": "Agrega un empleado al negocio. El dueño ya se registra automáticamente. Usa esto para agregar empleados adicionales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del empleado",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Número de WhatsApp del empleado (ej: 5512345678)",
                },
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de nombres de servicios que hace este empleado. Si hace todos, omitir.",
                },
            },
            "required": ["name", "phone_number"],
        },
    },
    {
        "name": "save_business_hours",
        "description": "Guarda el horario de atención del negocio. Solo usa si el usuario proporciona horarios específicos.",
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
        "description": "Finaliza el proceso de registro y crea la cuenta. Solo llama cuando: 1) tienes nombre del negocio, 2) al menos un servicio, 3) el usuario confirmó que está listo para activar su cuenta.",
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
    {
        "name": "send_dashboard_link",
        "description": "Envía el link al dashboard y explica cómo iniciar sesión. Úsalo después de completar el registro.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "provision_twilio_number",
        "description": "Provisiona un nuevo número de WhatsApp dedicado para el negocio usando Twilio. Úsalo cuando el usuario NO tiene una cuenta de WhatsApp Business existente y quiere que Yume le proporcione un número dedicado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country_code": {
                    "type": "string",
                    "description": "Código de país para el número (MX para México, US para Estados Unidos). Default: MX",
                    "default": "MX",
                },
            },
        },
    },
]


def _format_service_menu(services: list[dict]) -> str:
    """Format services list as a nice menu display.

    Args:
        services: List of service dicts with name, price, duration_minutes

    Returns:
        Formatted menu string
    """
    if not services:
        return "Sin servicios aún"

    lines = []
    for svc in services:
        lines.append(f"• {svc['name']} - ${svc['price']:.0f} ({svc['duration_minutes']} min)")
    return "\n".join(lines)


def build_onboarding_system_prompt(session: OnboardingSession) -> str:
    """Build the system prompt for onboarding conversations.

    Args:
        session: Current onboarding session

    Returns:
        System prompt string
    """
    collected = session.collected_data or {}
    services = collected.get("services", [])
    staff_members = collected.get("staff", [])
    is_first_message = not collected.get("business_name") and not services

    # Build current progress summary
    progress_parts = []
    if collected.get("business_name"):
        progress_parts.append(f"• Negocio: {collected['business_name']}")
    if collected.get("owner_name"):
        progress_parts.append(f"• Dueño: {collected['owner_name']}")
    if collected.get("address"):
        progress_parts.append(f"• Dirección: {collected['address']}")
    if collected.get("business_hours"):
        progress_parts.append("• Horario: Configurado")
    if services:
        progress_parts.append(f"• Servicios: {len(services)}")
        for svc in services:
            progress_parts.append(f"  - {svc['name']} - ${svc['price']:.0f} ({svc['duration_minutes']} min)")
    if staff_members:
        progress_parts.append(f"• Empleados adicionales: {len(staff_members)}")
        for st in staff_members:
            progress_parts.append(f"  - {st['name']} ({st.get('phone_number', 'sin tel')})")

    progress = "\n".join(progress_parts) if progress_parts else "Ninguna información recolectada aún."

    # Build menu display for AI reference
    menu_display = _format_service_menu(services)

    # Determine current step
    if not collected.get("business_name"):
        current_step = "Paso 1: Obtener nombre del negocio y del dueño"
    elif not services:
        current_step = "Paso 2: Obtener servicios (nombre, precio, duración)"
    else:
        current_step = "Paso 3: Confirmar datos y activar cuenta"

    return f"""Eres Yume, una asistente de inteligencia artificial que ayuda a negocios de belleza en México a automatizar sus citas por WhatsApp.

## IMPORTANTE: Primera Interacción
{"ESTA ES LA PRIMERA INTERACCIÓN. Debes presentarte con el mensaje de bienvenida completo." if is_first_message else "Ya te presentaste. Continúa con el flujo de registro."}

## Mensaje de Bienvenida (SOLO primera interacción)
Si es la primera interacción, responde EXACTAMENTE así:

"¡Hola! 👋 Soy Yume, tu asistente para agendar citas automáticamente.

Ayudo a negocios de belleza a que sus clientes agenden por WhatsApp sin que tengas que contestar cada mensaje.

En 2-3 minutos configuramos tu cuenta:
1️⃣ Nombre de tu negocio
2️⃣ Servicios con precios
3️⃣ ¡Listo!

¿Tienes un salón, barbería, o negocio de belleza?"

## Estado Actual del Registro
{progress}

## Menú de Servicios Actual
{menu_display}

## Paso Actual
{current_step}

## Flujo de Conversación

### Paso 1: Información del Negocio
- Pregunta primero si tienen un negocio de belleza
- Obtén: nombre del negocio, tipo (salon/barbershop/spa/nails), nombre del dueño
- Opcionalmente: dirección (útil para clientes)
- Usa herramienta `save_business_info` cuando tengas los datos básicos
- Después pregunta por los horarios de atención

### Paso 2: Horarios
- Pregunta qué días abren y en qué horario
- Ejemplo: "¿Qué días abren y en qué horario?"
- Si dan horario tipo "lunes a sábado de 10 a 8", usa `save_business_hours`
- Pregunta si cierran para comer o es horario corrido

### Paso 3: Servicios
- Pregunta qué servicios ofrecen con precio y duración
- Ejemplo: "Dime el nombre, cuánto dura y el precio. Ejemplo: 'Corte de cabello, 45 minutos, $150'"
- Por cada servicio mencionado, usa `add_service` INMEDIATAMENTE
- **IMPORTANTE**: Después de agregar servicios, MUESTRA el menú actualizado al usuario
- Formato: "Perfecto, registré N servicios:\n• Corte - $150 (30 min)\n• Barba - $100 (20 min)\n\n¿Falta algún servicio?"
- Pregunta si quieren agregar más servicios o si está completo

### Paso 4: Empleados (Opcional)
- Si tienen más de una persona, pregunta quién más atiende
- Para cada empleado necesitas: nombre y teléfono de WhatsApp
- Usa `add_staff_member` por cada empleado adicional
- Pregunta si todos hacen todos los servicios o hay especialidades
- El dueño ya se registra automáticamente con su número actual

### Paso 5: Número de WhatsApp
Cuando el usuario termine de agregar servicios:
- Usa `provision_twilio_number` para obtener un número de WhatsApp dedicado para el negocio
- Yume le asignará un número de México para que sus clientes puedan agendar citas

### Paso 6: Confirmación y Activación
- Muestra un resumen de todo lo configurado
- Pregunta "¿Todo correcto? ¿Activamos tu cuenta?"
- Si confirman, usa `complete_onboarding` para crear la cuenta
- Después usa `send_dashboard_link` para enviar el link al dashboard
- Explica que sus clientes podrán escribir al número configurado para agendar

## ⚠️ CRÍTICO: Completar el Registro
**DEBES llamar la herramienta `complete_onboarding` cuando:**
1. Tienes el nombre del negocio guardado (save_business_info ya fue llamada)
2. Tienes al menos un servicio (add_service ya fue llamada al menos una vez)
3. El usuario confirma que está listo ("sí", "listo", "activa", "ok", "perfecto", "correcto", etc.)

**NO esperes a que el usuario diga palabras exactas.** Si ya tienes la información mínima y el usuario da cualquier señal de confirmación, LLAMA `complete_onboarding` con confirmed=true.

**Ejemplos de confirmación del usuario:**
- "Sí, activa" → LLAMA complete_onboarding
- "Ok, listo" → LLAMA complete_onboarding
- "Perfecto" → LLAMA complete_onboarding
- "Está bien" → LLAMA complete_onboarding
- "Dale" → LLAMA complete_onboarding
- "Va" → LLAMA complete_onboarding

## Instrucciones Importantes
- Habla en español mexicano natural, usa "tú" no "usted"
- Sé concisa pero amable. Máximo 3-4 oraciones por mensaje
- Cuando el usuario mencione servicios, USA LA HERRAMIENTA add_service inmediatamente
- Interpreta formatos flexibles de entrada:
  - "Corte dama $250 45 min" → Corte dama, 45 min, $250
  - "Corte 150" → Corte, duración estándar 30 min, $150
- Si el usuario no sabe un precio exacto, sugiere precios típicos mexicanos:
  - Corte de cabello: $100-200 (30-45 min)
  - Tinte: $400-800 (90-120 min)
  - Manicure: $150-250 (30-45 min)
  - Pedicure: $200-350 (45-60 min)
  - Barba: $80-150 (20-30 min)
  - Peinado: $200-400 (45-60 min)
- SIEMPRE muestra el menú actualizado después de agregar servicios
- NO inventes información. Solo guarda lo que el usuario te diga
- Si el usuario quiere corregir algo, permítelo amablemente

## Restricciones
- NUNCA compartas información de otros negocios
- Si preguntan algo fuera del registro, redirige amablemente
- No hagas promesas sobre funcionalidades que no existen
- El servicio es GRATUITO durante el piloto - menciónalo si preguntan sobre costos
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

        This returns:
        - An active (in-progress) session if one exists
        - A COMPLETED session if one exists (caller should redirect to staff flow)
        - A new session if neither exists

        Args:
            phone_number: User's phone number
            sender_name: Name from WhatsApp profile

        Returns:
            Onboarding session (may be completed - caller should check state)
        """
        # First, check for a COMPLETED session - if exists, return it so caller
        # can redirect to the staff flow (this fixes the "restart onboarding" bug)
        result = await self.db.execute(
            select(OnboardingSession).where(
                OnboardingSession.phone_number == phone_number,
                OnboardingSession.state == OnboardingState.COMPLETED.value,
            )
        )
        completed_session = result.scalar_one_or_none()
        if completed_session:
            logger.info(f"Found completed onboarding session for {phone_number}")
            return completed_session

        # Then check for an active (in-progress) session
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
            state=OnboardingState.INITIATED.value,
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
        import time
        start_time = time.time()

        logger.info(
            f"\n{'='*60}\n"
            f"🔧 ONBOARDING TOOL EXECUTION\n"
            f"{'='*60}\n"
            f"   Phone: {session.phone_number}\n"
            f"   State: {session.state}\n"
            f"   Tool: {tool_name}\n"
            f"   Input: {tool_input}\n"
            f"{'='*60}"
        )

        collected = dict(session.collected_data or {})

        if tool_name == "save_business_info":
            collected["business_name"] = tool_input.get("business_name")
            collected["business_type"] = tool_input.get("business_type")
            collected["owner_name"] = tool_input.get("owner_name")
            if tool_input.get("address"):
                collected["address"] = tool_input.get("address")
            if tool_input.get("city"):
                collected["city"] = tool_input.get("city")
            session.collected_data = collected
            old_state = session.state
            session.state = OnboardingState.COLLECTING_SERVICES.value
            await self.db.flush()
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"   ✅ save_business_info: {collected['business_name']} "
                f"(state: {old_state} → {session.state}) ({elapsed_ms:.0f}ms)"
            )
            return {
                "success": True,
                "message": "Información del negocio guardada",
                "business_name": collected["business_name"],
                "owner_name": collected["owner_name"],
            }

        elif tool_name == "add_service":
            services = collected.get("services", [])
            new_service = {
                "name": tool_input.get("name"),
                "duration_minutes": tool_input.get("duration_minutes"),
                "price": tool_input.get("price"),
            }
            services.append(new_service)
            collected["services"] = services
            session.collected_data = collected
            await self.db.flush()

            # Return the full updated menu so AI can display it
            menu_items = []
            for svc in services:
                menu_items.append({
                    "name": svc["name"],
                    "price": f"${svc['price']:.0f}",
                    "duration": f"{svc['duration_minutes']} min"
                })

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"   ✅ add_service: {new_service['name']} "
                f"(${new_service['price']}, {new_service['duration_minutes']}min) "
                f"Total: {len(services)} services ({elapsed_ms:.0f}ms)"
            )
            return {
                "success": True,
                "message": f"Servicio '{new_service['name']}' agregado",
                "total_services": len(services),
                "current_menu": menu_items,
                "menu_display": _format_service_menu(services)
            }

        elif tool_name == "get_current_menu":
            services = collected.get("services", [])
            if not services:
                return {
                    "success": True,
                    "total_services": 0,
                    "current_menu": [],
                    "menu_display": "Sin servicios aún"
                }

            menu_items = []
            for svc in services:
                menu_items.append({
                    "name": svc["name"],
                    "price": f"${svc['price']:.0f}",
                    "duration": f"{svc['duration_minutes']} min"
                })

            return {
                "success": True,
                "total_services": len(services),
                "current_menu": menu_items,
                "menu_display": _format_service_menu(services)
            }

        elif tool_name == "add_staff_member":
            staff_list = collected.get("staff", [])
            phone = tool_input.get("phone_number", "")
            # Normalize phone number
            if phone and not phone.startswith("+"):
                if phone.startswith("52"):
                    phone = f"+{phone}"
                else:
                    phone = f"+52{phone}"

            new_staff = {
                "name": tool_input.get("name"),
                "phone_number": phone,
                "services": tool_input.get("services"),  # None means all services
            }
            staff_list.append(new_staff)
            collected["staff"] = staff_list
            session.collected_data = collected
            await self.db.flush()

            return {
                "success": True,
                "message": f"Empleado '{new_staff['name']}' agregado",
                "total_staff": len(staff_list) + 1,  # +1 for owner
                "staff_display": f"• {new_staff['name']} - {phone}",
            }

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
            logger.info(f"   🎯 complete_onboarding called with confirmed={tool_input.get('confirmed')}")

            if not tool_input.get("confirmed"):
                elapsed_ms = (time.time() - start_time) * 1000
                logger.warning(f"   ⚠️ complete_onboarding: User not confirmed ({elapsed_ms:.0f}ms)")
                return {"success": False, "message": "El usuario no confirmó"}

            # Verify we have minimum required data
            if not collected.get("business_name"):
                elapsed_ms = (time.time() - start_time) * 1000
                logger.warning(f"   ⚠️ complete_onboarding: Missing business_name ({elapsed_ms:.0f}ms)")
                return {"success": False, "error": "Falta el nombre del negocio"}
            if not collected.get("services"):
                elapsed_ms = (time.time() - start_time) * 1000
                logger.warning(f"   ⚠️ complete_onboarding: Missing services ({elapsed_ms:.0f}ms)")
                return {"success": False, "error": "Falta al menos un servicio"}

            # Create the organization and all related entities
            try:
                logger.info(f"   📦 Creating organization: {collected.get('business_name')}")
                org = await self._create_organization(session)
                session.state = OnboardingState.COMPLETED.value
                session.organization_id = str(org.id)
                await self.db.flush()
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"\n{'🎉'*20}\n"
                    f"   ONBOARDING COMPLETED!\n"
                    f"   Business: {org.name}\n"
                    f"   Org ID: {org.id}\n"
                    f"   Phone: {session.phone_number}\n"
                    f"   Duration: {elapsed_ms:.0f}ms\n"
                    f"{'🎉'*20}"
                )
                return {
                    "success": True,
                    "message": "Registro completado",
                    "organization_id": str(org.id),
                    "business_name": org.name,
                }
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(f"   ❌ Error creating organization: {e} ({elapsed_ms:.0f}ms)", exc_info=True)
                return {"success": False, "error": str(e)}

        elif tool_name == "send_dashboard_link":
            business_name = collected.get("business_name", "tu negocio")
            dashboard_url = f"{_settings.frontend_url}/login"

            return {
                "success": True,
                "message": "Link del dashboard generado",
                "dashboard_url": dashboard_url,
                "business_name": business_name,
                "login_instructions": "Inicia sesión con tu número de WhatsApp, sin contraseña",
                "formatted_message": (
                    f"¡Felicidades! Tu cuenta de {business_name} está activa.\n\n"
                    f"📱 Dashboard: {dashboard_url}\n"
                    f"(Inicia sesión con tu número de WhatsApp, sin contraseña)\n\n"
                    f"Tus clientes ya pueden escribirte por WhatsApp para agendar citas automáticamente."
                )
            }

        elif tool_name == "provision_twilio_number":
            # Verify we have minimum required data before provisioning
            if not collected.get("business_name"):
                return {"success": False, "error": "Primero necesito el nombre del negocio"}
            if not collected.get("services"):
                return {"success": False, "error": "Primero necesito al menos un servicio"}

            business_name = collected["business_name"]
            country_code = tool_input.get("country_code", "MX")

            try:
                # Provision a new Twilio WhatsApp number
                result = await provision_number_for_business(
                    business_name=business_name,
                    webhook_base_url=_settings.app_base_url,
                    country_code=country_code,
                )

                if not result:
                    return {
                        "success": False,
                        "error": "No se pudo provisionar un número en este momento.",
                        "fallback_message": (
                            "No pudimos obtener un número nuevo en este momento. "
                            "Por favor intenta de nuevo más tarde o contacta soporte."
                        )
                    }

                # Store the provisioned number in session
                collected["twilio_provisioned_number"] = result["phone_number"]
                collected["twilio_phone_number_sid"] = result["phone_number_sid"]
                session.collected_data = collected
                await self.db.flush()

                logger.info(f"Provisioned Twilio number for {business_name}: {result['phone_number']}")

                return {
                    "success": True,
                    "message": "Número provisionado exitosamente",
                    "phone_number": result["phone_number"],
                    "phone_number_sid": result["phone_number_sid"],
                    "formatted_message": (
                        f"¡Listo! Te asigné el número {result['phone_number']} para tu negocio.\n\n"
                        f"Este será el número donde tus clientes pueden escribir para agendar citas.\n\n"
                        f"¿Quieres que active tu cuenta ahora?"
                    )
                }

            except Exception as e:
                logger.error(f"Error provisioning Twilio number: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                    "fallback_message": (
                        "Hubo un problema al obtener tu número. "
                        "Por favor intenta de nuevo más tarde o contacta soporte."
                    )
                }

        result = {"error": f"Unknown tool: {tool_name}"}
        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning(f"   ⚠️ Unknown tool: {tool_name} ({elapsed_ms:.0f}ms)")
        return result

    async def _create_organization(self, session: OnboardingSession) -> Organization:
        """Create organization and all related entities from session data.

        Args:
            session: Completed onboarding session

        Returns:
            Created organization
        """
        collected = session.collected_data
        logger.info(f"Creating organization from onboarding: {collected}")

        # Build address string
        address_parts = []
        if collected.get("address"):
            address_parts.append(collected["address"])
        if collected.get("city"):
            address_parts.append(collected["city"])
        full_address = ", ".join(address_parts) if address_parts else ""

        # Determine WhatsApp configuration:
        # Option 1: Twilio provisioned number (stored in collected_data)
        # Option 2: No WhatsApp setup yet (use owner's phone as placeholder)
        org_settings = {
            "language": "es",
            "currency": "MXN",
            "business_type": collected.get("business_type", "salon"),
        }

        if collected.get("twilio_provisioned_number"):
            # Twilio provisioned number path
            # Use the actual phone number for routing (NOT the SID)
            whatsapp_phone_number_id = collected["twilio_provisioned_number"]
            org_settings["whatsapp_provider"] = "twilio"
            org_settings["twilio_phone_number"] = collected["twilio_provisioned_number"]
            org_settings["twilio_phone_number_sid"] = collected["twilio_phone_number_sid"]
            logger.info(f"Using Twilio provisioned number: {collected['twilio_provisioned_number']}")
        else:
            # No WhatsApp setup yet - use owner phone as placeholder
            whatsapp_phone_number_id = session.phone_number
            org_settings["whatsapp_provider"] = "pending"  # Will be set when they provision a number
            logger.info(f"No WhatsApp number provisioned, using owner phone as placeholder")

        # 1. Create Organization
        org = Organization(
            name=collected["business_name"],
            phone_country_code=self._extract_country_code(session.phone_number),
            phone_number=session.phone_number,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            timezone="America/Mexico_City",
            status=OrganizationStatus.ACTIVE.value,
            settings=org_settings,
        )
        self.db.add(org)
        await self.db.flush()
        await self.db.refresh(org)
        logger.info(f"Created organization: {org.id}")

        # 2. Create Location
        location = Location(
            organization_id=org.id,
            name="Principal",
            address=full_address,
            business_hours=collected.get("business_hours", DEFAULT_BUSINESS_HOURS),
            is_primary=True,
        )
        self.db.add(location)
        await self.db.flush()
        await self.db.refresh(location)
        logger.info(f"Created location: {location.id}")

        # 3. Create Services
        services = []
        service_by_name = {}  # Map name to service for staff linking
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
            service_by_name[svc_data["name"].lower()] = service

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

        # 5. Create Staff (owner) with owner permission level
        owner_name = collected.get("owner_name") or session.owner_name or "Dueño"
        owner_staff = Staff(
            organization_id=org.id,
            location_id=location.id,
            default_spot_id=spot.id,
            name=owner_name,
            phone_number=session.phone_number,
            role=StaffRole.OWNER.value,
            permission_level=YumeUserPermissionLevel.OWNER.value,
            is_active=True,
            permissions={"can_manage_all": True},
        )
        self.db.add(owner_staff)
        await self.db.flush()
        await self.db.refresh(owner_staff)

        # Link owner to all services
        owner_staff.service_types.extend(services)
        logger.info(f"Created staff (owner): {owner_staff.id}")

        # 6. Create additional staff members collected during onboarding
        additional_staff = collected.get("staff", [])
        for staff_data in additional_staff:
            # Determine which services this staff member does
            staff_services = services  # Default: all services
            if staff_data.get("services"):
                # Filter to only specified services
                staff_services = []
                for svc_name in staff_data["services"]:
                    svc = service_by_name.get(svc_name.lower())
                    if svc:
                        staff_services.append(svc)
                # If no matches, assign all services
                if not staff_services:
                    staff_services = services

            employee = Staff(
                organization_id=org.id,
                location_id=location.id,
                default_spot_id=spot.id,
                name=staff_data["name"],
                phone_number=staff_data.get("phone_number", ""),
                role=StaffRole.EMPLOYEE.value,
                is_active=True,
                permissions={"can_view_schedule": True, "can_book": True},
            )
            self.db.add(employee)
            await self.db.flush()
            await self.db.refresh(employee)

            # Link employee to their services
            employee.service_types.extend(staff_services)
            logger.info(f"Created staff (employee): {employee.id} - {employee.name}")

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
