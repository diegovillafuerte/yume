"""Tool definitions and handlers for Claude AI.

Tools are the actions that Claude can take on behalf of users.
There are two sets of tools:
1. Customer tools - for booking, checking availability, etc.
2. Staff tools - for schedule management, walk-ins, etc.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Availability,
    AvailabilityType,
    Customer,
    Organization,
    ServiceType,
    Staff,
)
from app.services import scheduling as scheduling_service

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOMER TOOLS - Available to customers for booking
# =============================================================================

CUSTOMER_TOOLS = [
    {
        "name": "check_availability",
        "description": "Verifica los horarios disponibles para un servicio en un rango de fechas. Usa esta herramienta SIEMPRE antes de ofrecer horarios al cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio (ej: 'Corte de cabello', 'Manicure')",
                },
                "date_from": {
                    "type": "string",
                    "description": "Fecha inicial en formato YYYY-MM-DD",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha final en formato YYYY-MM-DD (opcional, si no se proporciona usa date_from)",
                },
                "preferred_staff_name": {
                    "type": "string",
                    "description": "Nombre del empleado preferido (opcional)",
                },
            },
            "required": ["service_name", "date_from"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Agenda una cita para el cliente. Solo usa esta herramienta después de confirmar el servicio, fecha y hora con el cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Nombre del servicio a agendar",
                },
                "start_time": {
                    "type": "string",
                    "description": "Fecha y hora de inicio en formato ISO (YYYY-MM-DDTHH:MM:SS)",
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
            "required": ["service_name", "start_time"],
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
        "description": "Transfiere la conversación al dueño del negocio cuando no puedes ayudar o el cliente lo solicita.",
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
]


# =============================================================================
# STAFF TOOLS - Available to staff for schedule management
# =============================================================================

STAFF_TOOLS = [
    {
        "name": "get_my_schedule",
        "description": "Obtiene la agenda personal del empleado para un rango de fechas.",
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
        "name": "get_business_schedule",
        "description": "Obtiene la agenda completa del negocio (todas las citas de todos los empleados).",
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
        "description": "Bloquea tiempo en la agenda del empleado (para comida, descanso, citas personales).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "Inicio del bloqueo en formato ISO (YYYY-MM-DDTHH:MM:SS)",
                },
                "end_time": {
                    "type": "string",
                    "description": "Fin del bloqueo en formato ISO (YYYY-MM-DDTHH:MM:SS)",
                },
                "reason": {
                    "type": "string",
                    "description": "Razón del bloqueo (opcional)",
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
            },
            "required": ["service_name"],
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
]


# =============================================================================
# TOOL HANDLERS - Functions that execute the tools
# =============================================================================


class ToolHandler:
    """Handles tool execution for AI conversations."""

    def __init__(self, db: AsyncSession, organization: Organization):
        """Initialize tool handler.

        Args:
            db: Database session
            organization: Current organization
        """
        self.db = db
        self.org = organization

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

        # Route to appropriate handler
        handlers = {
            # Customer tools
            "check_availability": self._check_availability,
            "book_appointment": lambda inp: self._book_appointment(inp, customer),
            "get_my_appointments": lambda inp: self._get_my_appointments(customer),
            "cancel_appointment": self._cancel_appointment,
            "reschedule_appointment": self._reschedule_appointment,
            "handoff_to_human": self._handoff_to_human,
            # Staff tools
            "get_my_schedule": lambda inp: self._get_my_schedule(inp, staff),
            "get_business_schedule": self._get_business_schedule,
            "block_time": lambda inp: self._block_time(inp, staff),
            "mark_appointment_status": self._mark_appointment_status,
            "book_walk_in": lambda inp: self._book_walk_in(inp, staff),
            "get_customer_history": self._get_customer_history,
            "cancel_customer_appointment": self._cancel_customer_appointment,
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
        service_name = tool_input.get("service_name", "")
        date_from_str = tool_input.get("date_from", "")
        date_to_str = tool_input.get("date_to", date_from_str)

        # Find service by name
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
            available_services = [s.name for s in services_result.scalars().all()]
            return {
                "error": f"No encontré el servicio '{service_name}'",
                "available_services": available_services,
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

        # Get available slots
        slots = await scheduling_service.get_available_slots(
            db=self.db,
            organization_id=self.org.id,
            location_id=location.id,
            service_type_id=service.id,
            date_from=date_from,
            date_to=date_to,
        )

        if not slots:
            return {
                "service": service.name,
                "date_range": f"{date_from_str} a {date_to_str}",
                "slots": [],
                "message": "No hay horarios disponibles en este rango de fechas",
            }

        # Format slots for AI
        formatted_slots = []
        for slot in slots:
            formatted_slots.append({
                "date": slot.date.strftime("%Y-%m-%d"),
                "time": slot.start_time.strftime("%I:%M %p"),
                "staff_name": slot.staff_name,
                "staff_id": str(slot.staff_id),
            })

        return {
            "service": service.name,
            "price": f"${service.price_cents / 100:.0f} MXN",
            "duration": f"{service.duration_minutes} min",
            "date_range": f"{date_from_str} a {date_to_str}",
            "slots": formatted_slots,
        }

    async def _book_appointment(
        self, tool_input: dict[str, Any], customer: Customer | None
    ) -> dict[str, Any]:
        """Book an appointment for the customer."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        service_name = tool_input.get("service_name", "")
        start_time_str = tool_input.get("start_time", "")
        customer_name = tool_input.get("customer_name")

        # Update customer name if provided
        if customer_name and not customer.name:
            customer.name = customer_name
            await self.db.flush()

        # Find service
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

        # Parse start time
        try:
            start_time = datetime.fromisoformat(start_time_str)
        except ValueError:
            return {"error": "Formato de fecha/hora inválido"}

        # Calculate end time
        end_time = start_time + timedelta(minutes=service.duration_minutes)

        # Find available staff (first available for now)
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

        # Create appointment
        appointment = Appointment(
            organization_id=self.org.id,
            location_id=location.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_type_id=service.id,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status=AppointmentStatus.CONFIRMED.value,
            source=AppointmentSource.WHATSAPP.value,
        )
        self.db.add(appointment)
        await self.db.flush()
        await self.db.refresh(appointment)

        return {
            "success": True,
            "appointment_id": str(appointment.id),
            "service": service.name,
            "date": start_time.strftime("%A %d de %B"),
            "time": start_time.strftime("%I:%M %p"),
            "staff": staff.name,
            "price": f"${service.price_cents / 100:.0f} MXN",
            "duration": f"{service.duration_minutes} min",
        }

    async def _get_my_appointments(
        self, customer: Customer | None
    ) -> dict[str, Any]:
        """Get customer's upcoming appointments."""
        if not customer:
            return {"error": "No se pudo identificar al cliente"}

        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.customer_id == customer.id,
                Appointment.scheduled_start >= datetime.now(timezone.utc),
                Appointment.status.in_([
                    AppointmentStatus.PENDING.value,
                    AppointmentStatus.CONFIRMED.value,
                ]),
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
            staff = await self.db.get(Staff, apt.staff_id) if apt.staff_id else None

            formatted.append({
                "id": str(apt.id),
                "service": service.name if service else "Unknown",
                "date": apt.scheduled_start.strftime("%A %d de %B"),
                "time": apt.scheduled_start.strftime("%I:%M %p"),
                "staff": staff.name if staff else "Por asignar",
                "status": apt.status,
            })

        return {"appointments": formatted}

    async def _cancel_appointment(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Cancel an appointment."""
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

        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = reason
        await self.db.flush()

        return {
            "success": True,
            "message": "Cita cancelada correctamente",
            "appointment_id": appointment_id,
        }

    async def _reschedule_appointment(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Reschedule an appointment."""
        appointment_id = tool_input.get("appointment_id", "")
        new_start_time_str = tool_input.get("new_start_time", "")

        try:
            apt_uuid = UUID(appointment_id)
            new_start_time = datetime.fromisoformat(new_start_time_str)
        except ValueError:
            return {"error": "Parámetros inválidos"}

        appointment = await self.db.get(Appointment, apt_uuid)
        if not appointment or appointment.organization_id != self.org.id:
            return {"error": "Cita no encontrada"}

        # Get service duration
        service = await self.db.get(ServiceType, appointment.service_type_id)
        if not service:
            return {"error": "Servicio no encontrado"}

        new_end_time = new_start_time + timedelta(minutes=service.duration_minutes)

        appointment.scheduled_start = new_start_time
        appointment.scheduled_end = new_end_time
        await self.db.flush()

        return {
            "success": True,
            "message": "Cita reagendada correctamente",
            "new_date": new_start_time.strftime("%A %d de %B"),
            "new_time": new_start_time.strftime("%I:%M %p"),
        }

    async def _handoff_to_human(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Handoff conversation to business owner."""
        reason = tool_input.get("reason", "Solicitud del cliente")

        # TODO: Implement actual notification to owner
        # For now, just acknowledge the handoff

        return {
            "success": True,
            "message": f"Conversación transferida al dueño del negocio. Razón: {reason}",
            "notify_owner": True,
        }

    # -------------------------------------------------------------------------
    # Staff Tool Implementations
    # -------------------------------------------------------------------------

    async def _get_my_schedule(
        self, tool_input: dict[str, Any], staff: Staff | None
    ) -> dict[str, Any]:
        """Get staff member's schedule."""
        if not staff:
            return {"error": "No se pudo identificar al empleado"}

        date_from_str = tool_input.get("date_from", datetime.now().strftime("%Y-%m-%d"))
        date_to_str = tool_input.get("date_to", date_from_str)

        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
        except ValueError:
            return {"error": "Formato de fecha inválido"}

        # Get appointments for this staff
        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.staff_id == staff.id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to + timedelta(days=1),
                Appointment.status.in_([
                    AppointmentStatus.PENDING.value,
                    AppointmentStatus.CONFIRMED.value,
                ]),
            )
            .order_by(Appointment.scheduled_start)
        )
        appointments = result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            customer = await self.db.get(Customer, apt.customer_id)

            formatted.append({
                "time": apt.scheduled_start.strftime("%I:%M %p"),
                "service": service.name if service else "Unknown",
                "customer": customer.name if customer and customer.name else "Cliente",
                "status": apt.status,
            })

        return {
            "staff_name": staff.name,
            "date_range": f"{date_from_str} a {date_to_str}",
            "appointments": formatted,
            "count": len(formatted),
        }

    async def _get_business_schedule(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Get full business schedule."""
        date_from_str = tool_input.get("date_from", datetime.now().strftime("%Y-%m-%d"))
        date_to_str = tool_input.get("date_to", date_from_str)

        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
        except ValueError:
            return {"error": "Formato de fecha inválido"}

        result = await self.db.execute(
            select(Appointment)
            .where(
                Appointment.organization_id == self.org.id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to + timedelta(days=1),
                Appointment.status.in_([
                    AppointmentStatus.PENDING.value,
                    AppointmentStatus.CONFIRMED.value,
                ]),
            )
            .order_by(Appointment.scheduled_start)
        )
        appointments = result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            customer = await self.db.get(Customer, apt.customer_id)
            staff = await self.db.get(Staff, apt.staff_id) if apt.staff_id else None

            formatted.append({
                "time": apt.scheduled_start.strftime("%I:%M %p"),
                "staff": staff.name if staff else "Sin asignar",
                "service": service.name if service else "Unknown",
                "customer": customer.name if customer and customer.name else "Cliente",
            })

        return {
            "business": self.org.name,
            "date_range": f"{date_from_str} a {date_to_str}",
            "appointments": formatted,
            "count": len(formatted),
        }

    async def _block_time(
        self, tool_input: dict[str, Any], staff: Staff | None
    ) -> dict[str, Any]:
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

        # Create availability exception (blocked = not available)
        availability = Availability(
            staff_id=staff.id,
            type=AvailabilityType.EXCEPTION.value,
            exception_date=start_time.date(),
            start_time=start_time.time(),
            end_time=end_time.time(),
            is_available=False,
        )
        self.db.add(availability)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Tiempo bloqueado de {start_time.strftime('%I:%M %p')} a {end_time.strftime('%I:%M %p')}",
            "reason": reason,
        }

    async def _mark_appointment_status(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
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

        service_name = tool_input.get("service_name", "")
        customer_phone = tool_input.get("customer_phone")
        customer_name = tool_input.get("customer_name")

        # Find service
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
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(minutes=service.duration_minutes)

        appointment = Appointment(
            organization_id=self.org.id,
            location_id=location.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_type_id=service.id,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status=AppointmentStatus.CONFIRMED.value,
            source=AppointmentSource.WALK_IN.value,
        )
        self.db.add(appointment)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Walk-in registrado: {customer.name or 'Cliente'} para {service.name}",
            "staff": staff.name,
            "service": service.name,
        }

    async def _get_customer_history(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
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
            .where(Appointment.customer_id == customer.id)
            .order_by(Appointment.scheduled_start.desc())
            .limit(10)
        )
        appointments = result.scalars().all()

        formatted = []
        for apt in appointments:
            service = await self.db.get(ServiceType, apt.service_type_id)
            formatted.append({
                "date": apt.scheduled_start.strftime("%Y-%m-%d"),
                "time": apt.scheduled_start.strftime("%I:%M %p"),
                "service": service.name if service else "Unknown",
                "status": apt.status,
            })

        return {
            "customer_name": customer.name or "Sin nombre",
            "customer_phone": customer.phone_number,
            "total_appointments": len(appointments),
            "history": formatted,
        }

    async def _cancel_customer_appointment(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
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
