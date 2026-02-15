"""Tool definitions and handlers for Claude AI.

Tools are the actions that Claude can take on behalf of users.
There are two sets of tools:
1. Customer tools - for booking, checking availability, etc.
2. Staff tools - for schedule management, walk-ins, etc.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Availability,
    AvailabilityType,
    Conversation,
    ConversationStatus,
    Customer,
    Organization,
    ServiceType,
    Staff,
)
from app.services import scheduling as scheduling_service
from app.services.permissions import (
    TOOL_PERMISSION_MAP,
    can_use_tool,
    get_permission_denied_message,
)
from app.services.tracing import traced

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOMER TOOLS - Available to customers for booking
# =============================================================================

CUSTOMER_TOOLS = [
    {
        "name": "check_availability",
        "description": "Verifica los horarios disponibles para un servicio. Usa esta herramienta SIEMPRE antes de ofrecer horarios al cliente. Interpreta fechas relativas: 'mañana' = tomorrow's date, 'esta semana' = today to end of week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "ID del servicio (UUID). Si está disponible, úsalo en lugar del nombre.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio (ej: 'Corte de cabello', 'Manicure'). Puede ser parcial.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Fecha inicial en formato YYYY-MM-DD. Usa la fecha actual si el cliente dice 'hoy', mañana si dice 'mañana', etc.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha final en formato YYYY-MM-DD. Para 'esta semana' usa el próximo domingo. Para un día específico, omite este campo.",
                },
                "preferred_staff_id": {
                    "type": "string",
                    "description": "ID del empleado preferido (opcional).",
                },
                "preferred_staff_name": {
                    "type": "string",
                    "description": "Nombre del empleado preferido (opcional). Si el cliente dice 'con María', pasa 'María' aquí.",
                },
            },
            "required": ["date_from"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Agenda una cita para el cliente. Solo usa esta herramienta después de confirmar el servicio, fecha y hora con el cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "ID del servicio a agendar (UUID). Si está disponible, úsalo.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio a agendar",
                },
                "start_time": {
                    "type": "string",
                    "description": "Fecha y hora de inicio en formato ISO (YYYY-MM-DDTHH:MM:SS)",
                },
                "staff_id": {
                    "type": "string",
                    "description": "ID del empleado (opcional)",
                },
                "staff_name": {
                    "type": "string",
                    "description": "Nombre del empleado (opcional)",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Nombre del cliente (si lo proporcionó)",
                },
            },
            "required": ["start_time"],
        },
    },
    {
        "name": "get_my_appointments",
        "description": "Obtiene las próximas citas del cliente actual.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancela una cita existente del cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID de la cita a cancelar",
                },
                "reason": {
                    "type": "string",
                    "description": "Razón de la cancelación (opcional)",
                },
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Reagenda una cita existente a un nuevo horario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID de la cita a reagendar",
                },
                "new_start_time": {
                    "type": "string",
                    "description": "Nueva fecha y hora en formato ISO (YYYY-MM-DDTHH:MM:SS)",
                },
            },
            "required": ["appointment_id", "new_start_time"],
        },
    },
    {
        "name": "handoff_to_human",
        "description": "Transfiere la conversación al dueño del negocio. SOLO usa esta herramienta cuando el cliente EXPLÍCITAMENTE pida hablar con una persona real (ej: 'quiero hablar con alguien', 'pásame con el dueño'). NUNCA la uses por iniciativa propia.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Razón de la transferencia",
                },
            },
            "required": ["reason"],
        },
    },
    {
        "name": "update_customer_info",
        "description": "Actualiza la información del cliente (nombre). Usa esta herramienta cuando el cliente proporcione su nombre durante la conversación.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del cliente",
                },
            },
            "required": ["name"],
        },
    },
]


# =============================================================================
# STAFF TOOLS - Available to staff for schedule management
# =============================================================================

STAFF_TOOLS = [
    {
        "name": "get_my_schedule",
        "description": "Obtiene la agenda personal del empleado para un día o rango de fechas. Si el staff dice 'hoy', usa la fecha actual. Si dice 'mañana', usa la fecha de mañana.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Fecha inicial en formato YYYY-MM-DD. Usa la fecha del prompt del sistema para 'hoy' o 'mañana'.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha final en formato YYYY-MM-DD (opcional, si no se proporciona usa date_from)",
                },
            },
        },
    },
    {
        "name": "get_business_schedule",
        "description": "Obtiene la agenda completa del negocio (todas las citas de todos los empleados). Solo para dueños o con permiso.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Fecha inicial en formato YYYY-MM-DD (por defecto hoy)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha final en formato YYYY-MM-DD (por defecto igual a date_from)",
                },
            },
        },
    },
    {
        "name": "block_time",
        "description": "Bloquea tiempo en la agenda del empleado (para comida, descanso, citas personales). El staff puede decir 'bloquea de 2 a 3' y debes convertirlo a formato ISO con la fecha correcta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "Inicio del bloqueo en formato ISO (YYYY-MM-DDTHH:MM:SS). Convierte '2 PM' a '14:00:00'.",
                },
                "end_time": {
                    "type": "string",
                    "description": "Fin del bloqueo en formato ISO (YYYY-MM-DDTHH:MM:SS). Convierte '3 PM' a '15:00:00'.",
                },
                "reason": {
                    "type": "string",
                    "description": "Razón del bloqueo (ej: 'comida', 'descanso', 'cita personal')",
                },
            },
            "required": ["start_time", "end_time"],
        },
    },
    {
        "name": "mark_appointment_status",
        "description": "Marca una cita como completada, no-show o cancelada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID de la cita",
                },
                "status": {
                    "type": "string",
                    "enum": ["completed", "no_show", "cancelled"],
                    "description": "Nuevo estado de la cita",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales (opcional)",
                },
            },
            "required": ["appointment_id", "status"],
        },
    },
    {
        "name": "book_walk_in",
        "description": "Registra un cliente que acaba de llegar sin cita (walk-in).",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "ID del servicio (UUID). Si está disponible, úsalo.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio",
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Teléfono del cliente (opcional)",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Nombre del cliente (opcional)",
                },
                "staff_id": {
                    "type": "string",
                    "description": "ID del empleado (opcional)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_customer_history",
        "description": "Consulta el historial de citas de un cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_phone": {
                    "type": "string",
                    "description": "Teléfono del cliente",
                },
            },
            "required": ["customer_phone"],
        },
    },
    {
        "name": "cancel_customer_appointment",
        "description": "Cancela una cita de un cliente y opcionalmente notifica al cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID de la cita a cancelar",
                },
                "reason": {
                    "type": "string",
                    "description": "Razón de la cancelación",
                },
                "notify_customer": {
                    "type": "boolean",
                    "description": "¿Enviar mensaje al cliente?",
                },
            },
            "required": ["appointment_id"],
        },
    },
    # Owner/Admin management tools
    {
        "name": "get_business_stats",
        "description": "Obtiene estadísticas del negocio (solo para dueños y administradores). Incluye citas totales, ingresos estimados, y métricas de rendimiento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Fecha inicial en formato YYYY-MM-DD (por defecto hace 30 días)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha final en formato YYYY-MM-DD (por defecto hoy)",
                },
            },
        },
    },
    {
        "name": "add_staff_member",
        "description": "Agrega un nuevo empleado al negocio (solo para dueños y administradores). El empleado recibirá un mensaje de WhatsApp para completar su configuración.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del empleado",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Número de WhatsApp del empleado (ej: +521234567890)",
                },
                "permission_level": {
                    "type": "string",
                    "enum": ["admin", "staff", "viewer"],
                    "description": "Nivel de permisos (admin, staff, o viewer). Por defecto: staff",
                },
            },
            "required": ["name", "phone_number"],
        },
    },
    {
        "name": "remove_staff_member",
        "description": "Desactiva un empleado del negocio (solo para dueños y administradores). El empleado ya no podrá acceder al sistema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "staff_name": {
                    "type": "string",
                    "description": "Nombre del empleado a remover",
                },
                "staff_phone": {
                    "type": "string",
                    "description": "O su número de teléfono",
                },
            },
        },
    },
    {
        "name": "change_staff_permission",
        "description": "Cambia el nivel de permisos de un empleado (solo para dueños). Niveles: admin (puede gestionar empleados), staff (puede ver agenda y crear citas), viewer (solo lectura).",
        "input_schema": {
            "type": "object",
            "properties": {
                "staff_name": {
                    "type": "string",
                    "description": "Nombre del empleado",
                },
                "new_permission_level": {
                    "type": "string",
                    "enum": ["admin", "staff", "viewer"],
                    "description": "Nuevo nivel de permisos",
                },
            },
            "required": ["staff_name", "new_permission_level"],
        },
    },
    # Service management tools (owner only)
    {
        "name": "add_service",
        "description": "Agrega un nuevo servicio al menú del negocio (solo para dueños). Llama esta herramienta por cada servicio que el dueño quiera agregar.",
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
        "name": "update_service",
        "description": "Actualiza el precio o duración de un servicio existente (solo para dueños).",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio a actualizar",
                },
                "new_price": {
                    "type": "number",
                    "description": "Nuevo precio en pesos mexicanos (opcional)",
                },
                "new_duration_minutes": {
                    "type": "integer",
                    "description": "Nueva duración en minutos (opcional)",
                },
                "new_name": {
                    "type": "string",
                    "description": "Nuevo nombre del servicio (opcional)",
                },
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "remove_service",
        "description": "Desactiva un servicio del menú del negocio (solo para dueños). El servicio se desactiva pero no se borra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio a remover",
                },
            },
            "required": ["service_name"],
        },
    },
]


# =============================================================================
# TOOL HANDLERS - Functions that execute the tools
# =============================================================================


class ToolHandler:
    """Handles tool execution for AI conversations."""

    def __init__(self, db: AsyncSession, organization: Organization, mock_mode: bool = False):
        """Initialize tool handler.

        Args:
            db: Database session
            organization: Current organization
            mock_mode: If True, WhatsApp messages are mocked (for simulation)
        """
        self.db = db
        self.org = organization
        self.mock_mode = mock_mode

    def _get_org_tz(self) -> ZoneInfo:
        """Get organization timezone."""
        return ZoneInfo(self.org.timezone) if self.org.timezone else ZoneInfo("America/Mexico_City")

    def _to_local(self, utc_dt: datetime) -> datetime:
        """Convert UTC datetime to org local time."""
        return utc_dt.astimezone(self._get_org_tz())

    def _to_utc(self, naive_or_local_dt: datetime) -> datetime:
        """Convert naive/local datetime to UTC. Treats naive as org-local."""
        if naive_or_local_dt.tzinfo is None:
            return naive_or_local_dt.replace(tzinfo=self._get_org_tz()).astimezone(UTC)
        return naive_or_local_dt.astimezone(UTC)

    @traced(trace_type="ai_tool", capture_args=["tool_name", "tool_input"])
    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        customer: Customer | None = None,
        staff: Staff | None = None,
    ) -> dict[str, Any]:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            customer: Customer context (for customer tools)
            staff: Staff context (for staff tools)

        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

        # Check permissions for staff tools
        if staff and tool_name in TOOL_PERMISSION_MAP:
            if not can_use_tool(staff, tool_name):
                action = TOOL_PERMISSION_MAP.get(tool_name, tool_name)
                error_msg = get_permission_denied_message(action, staff)
                logger.warning(
                    f"Permission denied: {staff.name} ({staff.permission_level}) "
                    f"tried to use {tool_name}"
                )
                return {
                    "error": error_msg,
                    "permission_denied": True,
                    "required_action": action,
                }

        # Route to appropriate handler
        handlers = {
            # Customer tools
            "check_availability": self._check_availability,
            "book_appointment": lambda inp: self._book_appointment(inp, customer),
            "get_my_appointments": lambda inp: self._get_my_appointments(customer),
            "cancel_appointment": lambda inp: self._cancel_appointment(inp, customer),
            "reschedule_appointment": lambda inp: self._reschedule_appointment(inp, customer),
            "handoff_to_human": lambda inp: self._handoff_to_human(inp, customer),
            "update_customer_info": lambda inp: self._update_customer_info(inp, customer),
            # Staff tools
            "get_my_schedule": lambda inp: self._get_my_schedule(inp, staff),
            "get_business_schedule": self._get_business_schedule,
            "block_time": lambda inp: self._block_time(inp, staff),
            "mark_appointment_status": self._mark_appointment_status,
            "book_walk_in": lambda inp: self._book_walk_in(inp, staff),
            "get_customer_history": self._get_customer_history,
            "cancel_customer_appointment": self._cancel_customer_appointment,
            # Management tools (owner/admin)
            "get_business_stats": self._get_business_stats,
            "add_staff_member": lambda inp: self._add_staff_member(inp, staff),
            "remove_staff_member": self._remove_staff_member,
            "change_staff_permission": self._change_staff_permission,
            "add_service": self._add_service,
            "update_service": self._update_service,
            "remove_service": self._remove_service,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await handler(tool_input)
            logger.info(f"Tool {tool_name} result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # Customer Tool Implementations
    # -------------------------------------------------------------------------

    async def _check_availability(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Check available appointment slots."""
        service_id = tool_input.get("service_id")
        service_name = tool_input.get("service_name", "")
        date_from_str = tool_input.get("date_from", "")
        date_to_str = tool_input.get("date_to", date_from_str)
        preferred_staff_id = tool_input.get("preferred_staff_id")
        preferred_staff = tool_input.get("preferred_staff_name")

        service = None
        if service_id:
            try:
                service_uuid = UUID(service_id)
            except ValueError:
                return {"error": "ID de servicio inválido"}

            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.id == service_uuid,
                    ServiceType.organization_id == self.org.id,
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()
            if not service:
                return {"error": f"Servicio con ID {service_id} no encontrado"}
        else:
            # Find service by name (fuzzy match)
            if not service_name:
                return {"error": "Debes indicar un servicio"}

            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.organization_id == self.org.id,
                    ServiceType.name.ilike(f"%{service_name}%"),
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()

        if not service:
            # Return available services
            services_result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.organization_id == self.org.id,
                    ServiceType.is_active == True,
                )
            )
            available_services = [
                f"{s.name} (ID: {s.id}) - ${s.price_cents / 100:.0f} ({s.duration_minutes} min)"
                for s in services_result.scalars().all()
            ]
            return {
                "error": f"No encontré el servicio '{service_name}'",
                "available_services": available_services,
                "suggestion": "Pregunta al cliente qué servicio de la lista desea",
            }

        # Parse dates
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Formato de fecha inválido. Usa YYYY-MM-DD"}

        # Get location (use primary location)
        from app.models import Location

        location_result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        location = location_result.scalar_one_or_none()

        if not location:
            return {"error": "No hay ubicación configurada para el negocio"}

        # If preferred staff specified, find their ID
        staff_id = None
        if preferred_staff_id:
            try:
                staff_uuid = UUID(preferred_staff_id)
            except ValueError:
                return {"error": "ID de empleado inválido"}

            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.id == staff_uuid,
                    Staff.organization_id == self.org.id,
                    Staff.is_active == True,
                )
            )
            staff = staff_result.scalar_one_or_none()
            if not staff:
                return {"error": "Empleado no encontrado"}
            staff_id = staff.id
        elif preferred_staff:
            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.organization_id == self.org.id,
                    Staff.name.ilike(f"%{preferred_staff}%"),
                    Staff.is_active == True,
                )
            )
            staff = staff_result.scalar_one_or_none()
            if staff:
                staff_id = staff.id

        # Get available slots
        slots = await scheduling_service.get_available_slots(
            db=self.db,
            organization_id=self.org.id,
            location_id=location.id,
            service_type_id=service.id,
            date_from=date_from,
            date_to=date_to,
            staff_id=staff_id,
        )

        if not slots:
            # Try to suggest alternative dates
            return {
                "service": service.name,
                "price": f"${service.price_cents / 100:.0f}",
                "duration": f"{service.duration_minutes} min",
                "date_range": f"{date_from_str} a {date_to_str}",
                "slots": [],
                "message": "No hay horarios disponibles en este rango de fechas",
                "suggestion": "Pregunta al cliente si le sirve otra fecha",
            }

        # Group slots by date for clearer display (convert UTC → local)
        slots_by_date = {}
        for slot in slots:
            local_start = self._to_local(slot.start_time)
            date_key = local_start.strftime("%Y-%m-%d")
            day_name = local_start.strftime("%A")  # Day of week
            if date_key not in slots_by_date:
                slots_by_date[date_key] = {
                    "date": date_key,
                    "day_name": day_name,
                    "times": [],
                }
            slots_by_date[date_key]["times"].append(
                {
                    "time": local_start.strftime("%I:%M %p"),
                    "iso_time": slot.start_time.isoformat(),  # Keep UTC for booking
                    "staff_id": str(slot.staff_id),
                    "staff_name": slot.staff_name,
                }
            )

        # Format slots for AI - limit to first few per day to avoid overwhelming
        formatted_slots = []
        for date_info in list(slots_by_date.values())[:5]:  # Max 5 days
            day_slots = {
                "date": date_info["date"],
                "day_name": date_info["day_name"],
                "times": date_info["times"][:6],  # Max 6 times per day
            }
            formatted_slots.append(day_slots)

        # Create a human-readable summary
        total_slots = sum(len(d["times"]) for d in formatted_slots)

        return {
            "service": service.name,
            "service_id": str(service.id),
            "price": f"${service.price_cents / 100:.0f}",
            "duration": f"{service.duration_minutes} min",
            "date_range": f"{date_from_str} a {date_to_str}",
            "total_available": total_slots,
            "slots_by_date": formatted_slots,
            "note": "Ofrece 3-4 opciones al cliente, no todos los horarios",
        }

    async def _book_appointment(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Book an appointment for the customer."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        service_id = tool_input.get("service_id")
        service_name = tool_input.get("service_name", "")
        start_time_str = tool_input.get("start_time", "")
        customer_name = tool_input.get("customer_name")
        staff_name = tool_input.get("staff_name")
        staff_id_input = tool_input.get("staff_id")

        # Update customer name if provided
        if customer_name and not customer.name:
            customer.name = customer_name
            await self.db.flush()

        # Find service
        service = None
        if service_id:
            try:
                service_uuid = UUID(service_id)
            except ValueError:
                return {"error": "ID de servicio inválido"}

            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.id == service_uuid,
                    ServiceType.organization_id == self.org.id,
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()
            if not service:
                return {"error": f"Servicio con ID '{service_id}' no encontrado"}
        else:
            if not service_name:
                return {"error": "Debes indicar un servicio"}
            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.organization_id == self.org.id,
                    ServiceType.name.ilike(f"%{service_name}%"),
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()

            if not service:
                return {"error": f"Servicio '{service_name}' no encontrado"}

        # Parse start time (treat naive as org-local, convert to UTC)
        try:
            start_time = datetime.fromisoformat(start_time_str)
            start_time = self._to_utc(start_time)
        except ValueError:
            return {"error": "Formato de fecha/hora inválido"}

        # Calculate end time
        end_time = start_time + timedelta(minutes=service.duration_minutes)

        # Find staff - prefer specified staff, otherwise first available
        if staff_id_input:
            try:
                staff_uuid = UUID(staff_id_input)
            except ValueError:
                return {"error": "ID de empleado inválido"}

            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.id == staff_uuid,
                    Staff.organization_id == self.org.id,
                    Staff.is_active == True,
                )
            )
            staff = staff_result.scalar_one_or_none()
            if not staff:
                return {"error": f"No encontré al empleado con ID '{staff_id_input}'"}
        elif staff_name:
            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.organization_id == self.org.id,
                    Staff.name.ilike(f"%{staff_name}%"),
                    Staff.is_active == True,
                )
            )
            staff = staff_result.scalar_one_or_none()
            if not staff:
                return {"error": f"No encontré al empleado '{staff_name}'"}
        else:
            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.organization_id == self.org.id,
                    Staff.is_active == True,
                )
            )
            staff = staff_result.scalars().first()

        if not staff:
            return {"error": "No hay personal disponible"}

        # Get location
        from app.models import Location

        location_result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        location = location_result.scalar_one_or_none()

        if not location:
            return {"error": "No hay ubicación configurada"}

        # Use staff's default spot for conflict checking and appointment
        spot_id = staff.default_spot_id

        # Check for conflicts before creating
        conflicts = await scheduling_service.check_appointment_conflicts(
            db=self.db,
            organization_id=self.org.id,
            staff_id=staff.id,
            spot_id=spot_id,
            start_time=start_time,
            end_time=end_time,
        )

        if conflicts:
            conflict = conflicts[0]
            conflict_time = self._to_local(conflict.scheduled_start).strftime("%I:%M %p")
            return {
                "error": f"El horario no está disponible. {staff.name} ya tiene una cita a las {conflict_time}.",
                "suggestion": "Por favor pregunta al cliente por otro horario.",
            }

        # Create appointment
        appointment = Appointment(
            organization_id=self.org.id,
            location_id=location.id,
            end_customer_id=customer.id,
            parlo_user_id=staff.id,
            spot_id=spot_id,
            service_type_id=service.id,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status=AppointmentStatus.CONFIRMED.value,
            source=AppointmentSource.WHATSAPP.value,
        )
        self.db.add(appointment)
        try:
            await self.db.flush()
            await self.db.refresh(appointment)
        except IntegrityError:
            await self.db.rollback()
            return {
                "error": "El horario no está disponible. Ya existe una cita en ese horario.",
                "suggestion": "Por favor pregunta al cliente por otro horario.",
            }

        local_start = self._to_local(start_time)

        # Notify business owner(s) about the new booking (fire-and-forget)
        try:
            await self._notify_owners_new_booking(
                customer=customer,
                service=service,
                staff=staff,
                local_start=local_start,
            )
        except Exception as e:
            logger.error(f"Failed to send owner booking notification: {e}", exc_info=True)

        return {
            "success": True,
            "appointment_id": str(appointment.id),
            "service": service.name,
            "date": local_start.strftime("%A %d de %B"),
            "time": local_start.strftime("%I:%M %p"),
            "staff": staff.name,
            "price": f"${service.price_cents / 100:.0f} MXN",
            "duration": f"{service.duration_minutes} min",
        }

    async def _get_my_appointments(self, customer: Customer | None) -> dict[str, Any]:
        """Get customer's upcoming appointments."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.end_customer_id == customer.id,
                Appointment.scheduled_start >= datetime.now(UTC),
                Appointment.status.in_(
                    [
                        AppointmentStatus.PENDING.value,
                        AppointmentStatus.CONFIRMED.value,
                    ]
                ),
            )
            .order_by(Appointment.scheduled_start)
        )
        appointments = result.scalars().all()

        if not appointments:
            return {"appointments": [], "message": "No tienes citas próximas"}

        formatted = []
        for apt in appointments:
            # Load related data
            service = await self.db.get(ServiceType, apt.service_type_id)
            staff = await self.db.get(Staff, apt.parlo_user_id) if apt.parlo_user_id else None

            local_start = self._to_local(apt.scheduled_start)
            formatted.append(
                {
                    "id": str(apt.id),
                    "service": service.name if service else "Unknown",
                    "date": local_start.strftime("%A %d de %B"),
                    "time": local_start.strftime("%I:%M %p"),
                    "staff": staff.name if staff else "Por asignar",
                    "status": apt.status,
                }
            )

        return {"appointments": formatted}

    async def _cancel_appointment(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Cancel an appointment."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        appointment_id = tool_input.get("appointment_id", "")
        reason = tool_input.get("reason", "")

        try:
            apt_uuid = UUID(appointment_id)
        except ValueError:
            return {"error": "ID de cita inválido"}

        appointment = await self.db.get(Appointment, apt_uuid)
        if not appointment:
            return {"error": "Cita no encontrada"}

        if appointment.organization_id != self.org.id:
            return {"error": "Cita no encontrada"}

        # Verify customer owns this appointment
        if appointment.end_customer_id != customer.id:
            return {"error": "Esta cita no te pertenece"}

        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = reason
        await self.db.flush()

        return {
            "success": True,
            "message": "Cita cancelada correctamente",
            "appointment_id": appointment_id,
        }

    async def _reschedule_appointment(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Reschedule an appointment."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        appointment_id = tool_input.get("appointment_id", "")
        new_start_time_str = tool_input.get("new_start_time", "")

        try:
            apt_uuid = UUID(appointment_id)
            new_start_time = datetime.fromisoformat(new_start_time_str)
            new_start_time = self._to_utc(new_start_time)
        except ValueError:
            return {"error": "Parámetros inválidos"}

        appointment = await self.db.get(Appointment, apt_uuid)
        if not appointment or appointment.organization_id != self.org.id:
            return {"error": "Cita no encontrada"}

        # Verify customer owns this appointment
        if appointment.end_customer_id != customer.id:
            return {"error": "Esta cita no te pertenece"}

        # Get service duration
        service = await self.db.get(ServiceType, appointment.service_type_id)
        if not service:
            return {"error": "Servicio no encontrado"}

        new_end_time = new_start_time + timedelta(minutes=service.duration_minutes)

        # Check for conflicts (exclude current appointment from check)
        conflicts = await scheduling_service.check_appointment_conflicts(
            db=self.db,
            organization_id=self.org.id,
            staff_id=appointment.parlo_user_id,
            spot_id=appointment.spot_id,
            start_time=new_start_time,
            end_time=new_end_time,
            exclude_appointment_id=apt_uuid,  # Don't conflict with self
        )

        if conflicts:
            conflict = conflicts[0]
            conflict_time = self._to_local(conflict.scheduled_start).strftime("%I:%M %p")
            return {
                "error": f"El nuevo horario no está disponible. Ya hay una cita a las {conflict_time}.",
                "suggestion": "Por favor elige otro horario.",
            }

        appointment.scheduled_start = new_start_time
        appointment.scheduled_end = new_end_time
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            return {
                "error": "El nuevo horario no está disponible. Ya existe una cita en ese horario.",
                "suggestion": "Por favor elige otro horario.",
            }

        local_new = self._to_local(new_start_time)
        return {
            "success": True,
            "message": "Cita reagendada correctamente",
            "new_date": local_new.strftime("%A %d de %B"),
            "new_time": local_new.strftime("%I:%M %p"),
        }

    async def _handoff_to_human(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Handoff conversation to business owner via WhatsApp relay."""
        reason = tool_input.get("reason", "Solicitud del cliente")

        if not customer:
            return {"error": "No se pudo identificar al cliente para la transferencia."}

        from app.services.handoff import initiate_handoff

        # Find the customer's active conversation
        conversation = await self._get_customer_conversation(customer.id)
        if not conversation:
            return {"error": "No se encontró la conversación activa."}

        result = await initiate_handoff(
            db=self.db,
            org=self.org,
            customer=customer,
            conversation=conversation,
            reason=reason,
            mock_mode=self.mock_mode,
        )

        return result

    async def _get_customer_conversation(self, customer_id: UUID) -> Conversation | None:
        """Get the active conversation for a customer."""
        from app.models import Conversation

        result = await self.db.execute(
            select(Conversation).where(
                Conversation.organization_id == self.org.id,
                Conversation.end_customer_id == customer_id,
                Conversation.status == ConversationStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def _update_customer_info(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Update customer information."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        name = tool_input.get("name", "").strip()
        if not name:
            return {"error": "El nombre es requerido"}

        customer.name = name
        await self.db.flush()

        return {
            "success": True,
            "message": f"Nombre actualizado a '{name}'",
            "customer_name": name,
        }

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------

    async def _notify_owners_new_booking(
        self,
        customer: Customer,
        service: ServiceType,
        staff: Staff,
        local_start: datetime,
    ) -> None:
        """Notify business owner(s) about a new AI-booked appointment.

        Follows the same pattern as staff_onboarding._notify_owner_staff_onboarded.
        Errors are logged but never raised — booking must always succeed.

        Args:
            customer: Customer who booked
            service: Service booked
            staff: Staff assigned
            local_start: Appointment start in org-local time
        """
        from app.models import ParloUserPermissionLevel
        from app.services.whatsapp import WhatsAppClient, resolve_whatsapp_sender

        # Find owner(s)
        result = await self.db.execute(
            select(Staff).where(
                Staff.organization_id == self.org.id,
                Staff.permission_level == ParloUserPermissionLevel.OWNER.value,
                Staff.is_active == True,
            )
        )
        owners = result.scalars().all()

        if not owners:
            logger.warning(f"No owners found for org {self.org.name} (ID: {self.org.id})")
            return

        # Build notification message
        customer_display = customer.name or "Cliente"
        customer_phone = customer.phone_number or ""
        from app.ai.prompts import format_date_spanish

        date_str = format_date_spanish(local_start)
        price_str = f"${service.price_cents / 100:.0f}"

        message = (
            f"\U0001f4c5 \u00a1Nueva cita agendada!\n\n"
            f"Cliente: {customer_display} ({customer_phone})\n"
            f"Servicio: {service.name} ({price_str})\n"
            f"Fecha: {date_str}\n"
            f"Con: {staff.name}\n\n"
            f"Agendada autom\u00e1ticamente por Parlo."
        )

        # Send to each owner
        whatsapp = WhatsAppClient(mock_mode=self.mock_mode)
        try:
            for owner in owners:
                if owner.phone_number and owner.id != staff.id:
                    try:
                        from_number = (
                            resolve_whatsapp_sender(self.org) or self.org.whatsapp_phone_number_id
                        )
                        await whatsapp.send_text_message(
                            phone_number_id=self.org.whatsapp_phone_number_id or "",
                            to=owner.phone_number,
                            message=message,
                            from_number=from_number,
                        )
                        logger.info(f"Booking notification sent to owner {owner.name}")
                    except Exception as e:
                        logger.error(f"Failed to notify owner {owner.name}: {e}")
        finally:
            await whatsapp.close()

    # -------------------------------------------------------------------------
    # Staff Tool Implementations
    # -------------------------------------------------------------------------

    async def _get_my_schedule(
        self, tool_input: dict[str, Any], staff: Staff | None
    ) -> dict[str, Any]:
        """Get staff member's schedule."""
        if not staff:
            return {"error": "No se pudo identificar al empleado"}

        org_tz = self._get_org_tz()
        now_local = datetime.now(org_tz)
        date_from_str = tool_input.get("date_from", now_local.strftime("%Y-%m-%d"))
        date_to_str = tool_input.get("date_to", date_from_str)

        try:
            date_from_local = datetime.strptime(date_from_str, "%Y-%m-%d").replace(tzinfo=org_tz)
            date_to_local = datetime.strptime(date_to_str, "%Y-%m-%d").replace(tzinfo=org_tz)
            date_from_utc = date_from_local.astimezone(UTC)
            date_to_utc = (date_to_local + timedelta(days=1)).astimezone(UTC)
        except ValueError:
            return {"error": "Formato de fecha inválido"}

        # Get appointments for this staff
        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.parlo_user_id == staff.id,
                Appointment.scheduled_start >= date_from_utc,
                Appointment.scheduled_start < date_to_utc,
                Appointment.status.in_(
                    [
                        AppointmentStatus.PENDING.value,
                        AppointmentStatus.CONFIRMED.value,
                    ]
                ),
            )
            .order_by(Appointment.scheduled_start)
        )
        appointments = result.scalars().all()

        # Get blocked time for this staff (use local dates for exception lookup)
        blocked_result = await self.db.execute(
            select(Availability).where(
                Availability.parlo_user_id == staff.id,
                Availability.type == AvailabilityType.EXCEPTION.value,
                Availability.is_available == False,
                Availability.exception_date >= date_from_local.date(),
                Availability.exception_date <= date_to_local.date(),
            )
        )
        blocked_times = blocked_result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            customer = await self.db.get(Customer, apt.end_customer_id)

            local_start = self._to_local(apt.scheduled_start)
            local_end = self._to_local(apt.scheduled_end)
            formatted.append(
                {
                    "type": "appointment",
                    "time": local_start.strftime("%I:%M %p"),
                    "end_time": local_end.strftime("%I:%M %p"),
                    "service": service.name if service else "Unknown",
                    "customer": customer.name if customer and customer.name else "Cliente",
                    "customer_phone": customer.phone_number if customer else None,
                    "status": apt.status,
                    "appointment_id": str(apt.id),
                }
            )

        # Add blocked times
        for block in blocked_times:
            if block.start_time and block.end_time:
                formatted.append(
                    {
                        "type": "blocked",
                        "time": block.start_time.strftime("%I:%M %p"),
                        "end_time": block.end_time.strftime("%I:%M %p"),
                        "reason": "Bloqueado",
                    }
                )

        # Sort by time
        formatted.sort(key=lambda x: x["time"])

        # Build display string for easy AI formatting
        if not formatted:
            display = "No tienes citas programadas."
        else:
            lines = []
            for item in formatted:
                if item["type"] == "appointment":
                    lines.append(f"⏰ {item['time']} - {item['service']} - {item['customer']}")
                else:
                    lines.append(f"🚫 {item['time']} - {item['end_time']} - {item['reason']}")
            display = "\n".join(lines)

        is_single_day = date_from_str == date_to_str
        date_display = date_from_str if is_single_day else f"{date_from_str} a {date_to_str}"

        return {
            "staff_name": staff.name,
            "date": date_display,
            "appointments": formatted,
            "count": len([f for f in formatted if f["type"] == "appointment"]),
            "display": display,
        }

    async def _get_business_schedule(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Get full business schedule."""
        org_tz = self._get_org_tz()
        now_local = datetime.now(org_tz)
        date_from_str = tool_input.get("date_from", now_local.strftime("%Y-%m-%d"))
        date_to_str = tool_input.get("date_to", date_from_str)

        try:
            date_from_local = datetime.strptime(date_from_str, "%Y-%m-%d").replace(tzinfo=org_tz)
            date_to_local = datetime.strptime(date_to_str, "%Y-%m-%d").replace(tzinfo=org_tz)
            date_from_utc = date_from_local.astimezone(UTC)
            date_to_utc = (date_to_local + timedelta(days=1)).astimezone(UTC)
        except ValueError:
            return {"error": "Formato de fecha inválido"}

        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.organization_id == self.org.id,
                Appointment.scheduled_start >= date_from_utc,
                Appointment.scheduled_start < date_to_utc,
                Appointment.status.in_(
                    [
                        AppointmentStatus.PENDING.value,
                        AppointmentStatus.CONFIRMED.value,
                    ]
                ),
            )
            .order_by(Appointment.scheduled_start)
        )
        appointments = result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            customer = await self.db.get(Customer, apt.end_customer_id)
            staff = await self.db.get(Staff, apt.parlo_user_id) if apt.parlo_user_id else None

            local_start = self._to_local(apt.scheduled_start)
            formatted.append(
                {
                    "time": local_start.strftime("%I:%M %p"),
                    "staff": staff.name if staff else "Sin asignar",
                    "service": service.name if service else "Unknown",
                    "customer": customer.name if customer and customer.name else "Cliente",
                }
            )

        return {
            "business": self.org.name,
            "date_range": f"{date_from_str} a {date_to_str}",
            "appointments": formatted,
            "count": len(formatted),
        }

    async def _block_time(self, tool_input: dict[str, Any], staff: Staff | None) -> dict[str, Any]:
        """Block time in staff schedule."""
        if not staff:
            return {"error": "No se pudo identificar al empleado"}

        start_time_str = tool_input.get("start_time", "")
        end_time_str = tool_input.get("end_time", "")
        reason = tool_input.get("reason", "Tiempo bloqueado")

        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
        except ValueError:
            return {"error": "Formato de fecha/hora inválido"}

        # Availability exceptions store local date and time values,
        # so interpret naive datetimes as org-local
        if start_time.tzinfo is None:
            local_start = start_time
        else:
            local_start = start_time.astimezone(self._get_org_tz())

        if end_time.tzinfo is None:
            local_end = end_time
        else:
            local_end = end_time.astimezone(self._get_org_tz())

        # Create availability exception (blocked = not available)
        availability = Availability(
            parlo_user_id=staff.id,
            type=AvailabilityType.EXCEPTION.value,
            exception_date=local_start.date(),
            start_time=local_start.time(),
            end_time=local_end.time(),
            is_available=False,
        )
        self.db.add(availability)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Tiempo bloqueado de {local_start.strftime('%I:%M %p')} a {local_end.strftime('%I:%M %p')}",
            "reason": reason,
        }

    async def _mark_appointment_status(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Mark appointment status."""
        appointment_id = tool_input.get("appointment_id", "")
        status = tool_input.get("status", "")
        notes = tool_input.get("notes", "")

        try:
            apt_uuid = UUID(appointment_id)
        except ValueError:
            return {"error": "ID de cita inválido"}

        appointment = await self.db.get(Appointment, apt_uuid)
        if not appointment or appointment.organization_id != self.org.id:
            return {"error": "Cita no encontrada"}

        status_map = {
            "completed": AppointmentStatus.COMPLETED.value,
            "no_show": AppointmentStatus.NO_SHOW.value,
            "cancelled": AppointmentStatus.CANCELLED.value,
        }

        if status not in status_map:
            return {"error": f"Estado inválido: {status}"}

        appointment.status = status_map[status]
        if notes:
            appointment.notes = notes
        await self.db.flush()

        status_messages = {
            "completed": "completada",
            "no_show": "marcada como no-show",
            "cancelled": "cancelada",
        }

        return {
            "success": True,
            "message": f"Cita {status_messages[status]} ✓",
        }

    async def _book_walk_in(
        self, tool_input: dict[str, Any], staff: Staff | None
    ) -> dict[str, Any]:
        """Book a walk-in customer."""
        if not staff:
            return {"error": "No se pudo identificar al empleado"}

        service_id = tool_input.get("service_id")
        service_name = tool_input.get("service_name", "")
        customer_phone = tool_input.get("customer_phone")
        customer_name = tool_input.get("customer_name")
        staff_id_input = tool_input.get("staff_id")

        # Find service
        service = None
        if service_id:
            try:
                service_uuid = UUID(service_id)
            except ValueError:
                return {"error": "ID de servicio inválido"}

            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.id == service_uuid,
                    ServiceType.organization_id == self.org.id,
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()
            if not service:
                return {"error": f"Servicio con ID '{service_id}' no encontrado"}
        else:
            if not service_name:
                return {"error": "Debes indicar un servicio"}
            result = await self.db.execute(
                select(ServiceType).where(
                    ServiceType.organization_id == self.org.id,
                    ServiceType.name.ilike(f"%{service_name}%"),
                    ServiceType.is_active == True,
                )
            )
            service = result.scalar_one_or_none()

            if not service:
                return {"error": f"Servicio '{service_name}' no encontrado"}

        # Resolve staff (optional override)
        staff_to_use = staff
        if staff_id_input:
            try:
                staff_uuid = UUID(staff_id_input)
            except ValueError:
                return {"error": "ID de empleado inválido"}

            staff_result = await self.db.execute(
                select(Staff).where(
                    Staff.id == staff_uuid,
                    Staff.organization_id == self.org.id,
                    Staff.is_active == True,
                )
            )
            staff_override = staff_result.scalar_one_or_none()
            if not staff_override:
                return {"error": "Empleado no encontrado"}
            staff_to_use = staff_override

        # Get or create customer
        customer = None
        if customer_phone:
            from app.services import customer as customer_service

            customer = await customer_service.get_or_create_customer(
                self.db, self.org.id, customer_phone, name=customer_name
            )
        else:
            # Create anonymous customer
            customer = Customer(
                organization_id=self.org.id,
                phone_number=f"walk_in_{datetime.now().timestamp()}",
                name=customer_name or "Walk-in",
            )
            self.db.add(customer)
            await self.db.flush()

        # Get location
        from app.models import Location

        location_result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        location = location_result.scalar_one_or_none()

        if not location:
            return {"error": "No hay ubicación configurada"}

        # Create appointment starting now
        start_time = datetime.now(UTC)
        end_time = start_time + timedelta(minutes=service.duration_minutes)

        # Use staff's default spot for conflict checking and appointment
        spot_id = staff_to_use.default_spot_id

        # Check for conflicts before creating
        conflicts = await scheduling_service.check_appointment_conflicts(
            db=self.db,
            organization_id=self.org.id,
            staff_id=staff_to_use.id,
            spot_id=spot_id,
            start_time=start_time,
            end_time=end_time,
        )

        if conflicts:
            conflict = conflicts[0]
            conflict_end = self._to_local(conflict.scheduled_end).strftime("%I:%M %p")
            return {
                "error": f"No puedes registrar el walk-in ahora. Tienes una cita hasta las {conflict_end}.",
                "suggestion": "Espera a que termine la cita actual o asigna a otro empleado.",
            }

        appointment = Appointment(
            organization_id=self.org.id,
            location_id=location.id,
            end_customer_id=customer.id,
            parlo_user_id=staff_to_use.id,
            spot_id=spot_id,
            service_type_id=service.id,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status=AppointmentStatus.CONFIRMED.value,
            source=AppointmentSource.WALK_IN.value,
        )
        self.db.add(appointment)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            return {
                "error": "No puedes registrar el walk-in ahora. Ya existe una cita en ese horario.",
                "suggestion": "Espera a que termine la cita actual o asigna a otro empleado.",
            }

        return {
            "success": True,
            "message": f"Walk-in registrado: {customer.name or 'Cliente'} para {service.name}",
            "staff": staff_to_use.name,
            "service": service.name,
        }

    async def _get_customer_history(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Get customer appointment history."""
        customer_phone = tool_input.get("customer_phone", "")

        # Find customer
        result = await self.db.execute(
            select(Customer).where(
                Customer.organization_id == self.org.id,
                Customer.phone_number == customer_phone,
            )
        )
        customer = result.scalar_one_or_none()

        if not customer:
            return {"error": f"Cliente con teléfono {customer_phone} no encontrado"}

        # Get appointments
        result = await self.db.execute(
            select(Appointment)
            .where(Appointment.end_customer_id == customer.id)
            .order_by(Appointment.scheduled_start.desc())
            .limit(10)
        )
        appointments = result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            local_start = self._to_local(apt.scheduled_start)
            formatted.append(
                {
                    "date": local_start.strftime("%Y-%m-%d"),
                    "time": local_start.strftime("%I:%M %p"),
                    "service": service.name if service else "Unknown",
                    "status": apt.status,
                }
            )

        return {
            "customer_name": customer.name or "Sin nombre",
            "customer_phone": customer.phone_number,
            "total_appointments": len(appointments),
            "history": formatted,
        }

    async def _cancel_customer_appointment(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Cancel a customer's appointment."""
        appointment_id = tool_input.get("appointment_id", "")
        reason = tool_input.get("reason", "Cancelada por el negocio")
        notify_customer = tool_input.get("notify_customer", True)

        try:
            apt_uuid = UUID(appointment_id)
        except ValueError:
            return {"error": "ID de cita inválido"}

        appointment = await self.db.get(Appointment, apt_uuid)
        if not appointment or appointment.organization_id != self.org.id:
            return {"error": "Cita no encontrada"}

        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = reason
        await self.db.flush()

        result = {
            "success": True,
            "message": "Cita cancelada ✓",
        }

        if notify_customer:
            # TODO: Send notification to customer via WhatsApp
            result["notification"] = "Se notificará al cliente"

        return result

    # -------------------------------------------------------------------------
    # Management Tool Implementations (Owner/Admin)
    # -------------------------------------------------------------------------

    async def _get_business_stats(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Get business statistics."""
        from sqlalchemy import func

        date_from_str = tool_input.get("date_from")
        date_to_str = tool_input.get("date_to")

        # Default to last 30 days
        if not date_to_str:
            date_to = datetime.now(UTC)
        else:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=UTC
                )
            except ValueError:
                return {"error": "Formato de fecha inválido para date_to"}

        if not date_from_str:
            date_from = date_to - timedelta(days=30)
        else:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                return {"error": "Formato de fecha inválido para date_from"}

        # Get appointment counts by status
        result = await self.db.execute(
            select(
                Appointment.status,
                func.count(Appointment.id).label("count"),
            )
            .where(
                Appointment.organization_id == self.org.id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to,
            )
            .group_by(Appointment.status)
        )
        status_counts = {row.status: row.count for row in result.all()}

        total_appointments = sum(status_counts.values())
        completed = status_counts.get(AppointmentStatus.COMPLETED.value, 0)
        cancelled = status_counts.get(AppointmentStatus.CANCELLED.value, 0)
        no_shows = status_counts.get(AppointmentStatus.NO_SHOW.value, 0)

        # Calculate estimated revenue (from completed appointments)
        revenue_result = await self.db.execute(
            select(func.sum(ServiceType.price_cents))
            .join(Appointment, Appointment.service_type_id == ServiceType.id)
            .where(
                Appointment.organization_id == self.org.id,
                Appointment.status == AppointmentStatus.COMPLETED.value,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to,
            )
        )
        total_revenue_cents = revenue_result.scalar() or 0
        total_revenue = total_revenue_cents / 100

        # Get top services
        services_result = await self.db.execute(
            select(
                ServiceType.name,
                func.count(Appointment.id).label("count"),
            )
            .join(Appointment, Appointment.service_type_id == ServiceType.id)
            .where(
                Appointment.organization_id == self.org.id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to,
            )
            .group_by(ServiceType.name)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
        )
        top_services = [{"service": row.name, "count": row.count} for row in services_result.all()]

        # Calculate completion rate
        completion_rate = 0
        if total_appointments > 0:
            completion_rate = round((completed / total_appointments) * 100, 1)

        return {
            "period": f"{date_from.strftime('%Y-%m-%d')} a {date_to.strftime('%Y-%m-%d')}",
            "total_appointments": total_appointments,
            "completed": completed,
            "cancelled": cancelled,
            "no_shows": no_shows,
            "completion_rate": f"{completion_rate}%",
            "estimated_revenue": f"${total_revenue:,.0f} MXN",
            "top_services": top_services,
        }

    async def _add_staff_member(
        self, tool_input: dict[str, Any], current_staff: Staff | None
    ) -> dict[str, Any]:
        """Add a new staff member to the organization."""

        name = tool_input.get("name", "").strip()
        phone_number = tool_input.get("phone_number", "").strip()
        permission_level = tool_input.get("permission_level", "staff")

        if not name:
            return {"error": "El nombre es requerido"}
        if not phone_number:
            return {"error": "El número de teléfono es requerido"}

        # Normalize phone number
        phone_number = phone_number.replace(" ", "").replace("-", "")
        if not phone_number.startswith("+"):
            if phone_number.startswith("52"):
                phone_number = "+" + phone_number
            else:
                phone_number = "+52" + phone_number

        # Validate permission level
        valid_levels = ["admin", "staff", "viewer"]
        if permission_level not in valid_levels:
            return {"error": f"Nivel de permiso inválido. Usa: {', '.join(valid_levels)}"}

        # Check for existing staff with same phone
        existing = await self.db.execute(
            select(Staff).where(
                Staff.organization_id == self.org.id,
                Staff.phone_number == phone_number,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": f"Ya existe un empleado con el número {phone_number}"}

        # Get primary location
        from app.models import Location

        location_result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        location = location_result.scalar_one_or_none()

        # Create new staff member
        new_staff = Staff(
            organization_id=self.org.id,
            location_id=location.id if location else None,
            name=name,
            phone_number=phone_number,
            role="employee",
            permission_level=permission_level,
            is_active=True,
        )
        self.db.add(new_staff)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Empleado '{name}' agregado correctamente",
            "staff_name": name,
            "phone_number": phone_number,
            "permission_level": permission_level,
            "note": "El empleado recibirá un mensaje de bienvenida en WhatsApp cuando envíe su primer mensaje.",
        }

    async def _remove_staff_member(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Deactivate a staff member."""
        staff_name = tool_input.get("staff_name", "").strip()
        staff_phone = tool_input.get("staff_phone", "").strip()

        if not staff_name and not staff_phone:
            return {"error": "Proporciona el nombre o teléfono del empleado"}

        # Find the staff member
        query = select(Staff).where(
            Staff.organization_id == self.org.id,
            Staff.is_active == True,
        )

        if staff_name:
            query = query.where(Staff.name.ilike(f"%{staff_name}%"))
        elif staff_phone:
            # Normalize phone
            staff_phone = staff_phone.replace(" ", "").replace("-", "")
            query = query.where(Staff.phone_number.contains(staff_phone))

        result = await self.db.execute(query)
        staff = result.scalar_one_or_none()

        if not staff:
            return {"error": "Empleado no encontrado"}

        # Don't allow removing owners
        if staff.permission_level == "owner":
            return {"error": "No se puede remover al dueño del negocio"}

        # Deactivate (soft delete)
        staff.is_active = False
        await self.db.flush()

        return {
            "success": True,
            "message": f"Empleado '{staff.name}' desactivado",
            "staff_name": staff.name,
            "note": "El empleado ya no podrá acceder al sistema. Sus citas programadas no fueron afectadas.",
        }

    async def _change_staff_permission(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Change a staff member's permission level."""
        staff_name = tool_input.get("staff_name", "").strip()
        new_level = tool_input.get("new_permission_level", "").strip()

        if not staff_name:
            return {"error": "El nombre del empleado es requerido"}

        # Validate new level
        valid_levels = ["admin", "staff", "viewer"]
        if new_level not in valid_levels:
            return {"error": f"Nivel inválido. Opciones: {', '.join(valid_levels)}"}

        # Find the staff member
        result = await self.db.execute(
            select(Staff).where(
                Staff.organization_id == self.org.id,
                Staff.name.ilike(f"%{staff_name}%"),
                Staff.is_active == True,
            )
        )
        staff = result.scalar_one_or_none()

        if not staff:
            return {"error": f"Empleado '{staff_name}' no encontrado"}

        # Don't allow changing owner's permissions
        if staff.permission_level == "owner":
            return {"error": "No se pueden cambiar los permisos del dueño"}

        old_level = staff.permission_level
        staff.permission_level = new_level
        await self.db.flush()

        level_descriptions = {
            "admin": "administrador (puede gestionar empleados)",
            "staff": "empleado (puede ver agenda y crear citas)",
            "viewer": "visualizador (solo lectura)",
        }

        return {
            "success": True,
            "message": f"Permisos de '{staff.name}' actualizados",
            "staff_name": staff.name,
            "old_level": old_level,
            "new_level": new_level,
            "description": level_descriptions.get(new_level, new_level),
        }

    # -------------------------------------------------------------------------
    # Service Management Tool Implementations (Owner)
    # -------------------------------------------------------------------------

    async def _add_service(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Add a new service to the business menu."""
        name = tool_input.get("name", "").strip()
        duration_minutes = tool_input.get("duration_minutes")
        price = tool_input.get("price")

        if not name:
            return {"error": "El nombre del servicio es requerido"}
        if not duration_minutes or duration_minutes <= 0:
            return {"error": "La duración debe ser mayor a 0 minutos"}
        if price is None or price < 0:
            return {"error": "El precio debe ser mayor o igual a 0"}

        # Check for duplicate service name
        existing = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.name.ilike(name),
                ServiceType.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": f"Ya existe un servicio llamado '{name}'"}

        # Get primary location to find a spot to link services
        from app.models import Location, Spot

        location_result = await self.db.execute(
            select(Location).where(
                Location.organization_id == self.org.id,
                Location.is_primary == True,
            )
        )
        location = location_result.scalar_one_or_none()

        # Create the service
        new_service = ServiceType(
            organization_id=self.org.id,
            name=name,
            duration_minutes=int(duration_minutes),
            price_cents=int(price * 100),
            is_active=True,
        )
        self.db.add(new_service)
        await self.db.flush()
        await self.db.refresh(new_service)

        # Link service to all active spots in the location
        if location:
            spot_result = await self.db.execute(
                select(Spot).where(
                    Spot.location_id == location.id,
                    Spot.is_active == True,
                )
            )
            spots = spot_result.scalars().all()
            for spot in spots:
                from app.models import spot_service_types

                await self.db.execute(
                    spot_service_types.insert().values(
                        spot_id=spot.id,
                        service_type_id=new_service.id,
                    )
                )
            await self.db.flush()

        # Return updated menu
        all_services = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.is_active == True,
            )
        )
        menu = [
            f"• {s.name} - ${s.price_cents / 100:.0f} MXN ({s.duration_minutes} min)"
            for s in all_services.scalars().all()
        ]

        return {
            "success": True,
            "message": f"Servicio '{name}' agregado al menú",
            "service_name": name,
            "price": f"${price:.0f} MXN",
            "duration": f"{duration_minutes} min",
            "current_menu": "\n".join(menu),
        }

    async def _update_service(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Update an existing service."""
        service_name = tool_input.get("service_name", "").strip()
        new_price = tool_input.get("new_price")
        new_duration = tool_input.get("new_duration_minutes")
        new_name = tool_input.get("new_name", "").strip()

        if not service_name:
            return {"error": "El nombre del servicio es requerido"}

        # Find the service
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.name.ilike(f"%{service_name}%"),
                ServiceType.is_active == True,
            )
        )
        service = result.scalar_one_or_none()

        if not service:
            return {"error": f"Servicio '{service_name}' no encontrado"}

        changes = []
        if new_price is not None:
            old_price = service.price_cents / 100
            service.price_cents = int(new_price * 100)
            changes.append(f"precio: ${old_price:.0f} → ${new_price:.0f}")
        if new_duration is not None:
            old_duration = service.duration_minutes
            service.duration_minutes = int(new_duration)
            changes.append(f"duración: {old_duration} → {new_duration} min")
        if new_name:
            old_name = service.name
            service.name = new_name
            changes.append(f"nombre: {old_name} → {new_name}")

        if not changes:
            return {"error": "No se especificó ningún cambio"}

        await self.db.flush()

        return {
            "success": True,
            "message": f"Servicio actualizado: {', '.join(changes)}",
            "service_name": service.name,
        }

    async def _remove_service(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Deactivate a service from the menu."""
        service_name = tool_input.get("service_name", "").strip()

        if not service_name:
            return {"error": "El nombre del servicio es requerido"}

        # Find the service
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.organization_id == self.org.id,
                ServiceType.name.ilike(f"%{service_name}%"),
                ServiceType.is_active == True,
            )
        )
        service = result.scalar_one_or_none()

        if not service:
            return {"error": f"Servicio '{service_name}' no encontrado"}

        service.is_active = False
        await self.db.flush()

        return {
            "success": True,
            "message": f"Servicio '{service.name}' removido del menú",
            "service_name": service.name,
        }
