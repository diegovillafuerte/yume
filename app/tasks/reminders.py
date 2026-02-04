"""Appointment reminder tasks."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.reminders.check_and_send_reminders")
def check_and_send_reminders() -> dict:
    """
    Periodic task to check for appointments needing reminders.

    Runs every 5 minutes via Celery Beat.
    Finds appointments starting in 23-25 hours that haven't had reminders sent.
    """
    # Import here to avoid circular imports and to get fresh db session
    import asyncio

    async def _check_reminders():
        from sqlalchemy import and_, select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.config import get_settings
        from app.models import Appointment, AppointmentStatus

        settings = get_settings()
        engine = create_async_engine(settings.async_database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        now = datetime.now(timezone.utc)
        reminder_window_start = now + timedelta(hours=23)
        reminder_window_end = now + timedelta(hours=25)

        async with session_factory() as db:
            # Find appointments needing reminders
            query = select(Appointment).where(
                and_(
                    Appointment.scheduled_start >= reminder_window_start,
                    Appointment.scheduled_start <= reminder_window_end,
                    Appointment.status.in_([
                        AppointmentStatus.PENDING.value,
                        AppointmentStatus.CONFIRMED.value,
                    ]),
                    Appointment.reminder_sent_at.is_(None),
                )
            )

            result = await db.execute(query)
            appointments = result.scalars().all()

            sent_count = 0
            for appointment in appointments:
                # Queue individual reminder task
                send_appointment_reminder.delay(str(appointment.id))
                sent_count += 1

            return {"checked": len(appointments), "queued": sent_count}

        await engine.dispose()

    return asyncio.run(_check_reminders())


@celery_app.task(name="app.tasks.reminders.send_appointment_reminder")
def send_appointment_reminder(appointment_id: str) -> dict:
    """
    Send reminder for a specific appointment.

    Args:
        appointment_id: UUID of the appointment to send reminder for
    """
    import asyncio

    async def _send_reminder():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.orm import joinedload

        from app.config import get_settings
        from app.models import Appointment, EndCustomer, Organization, ServiceType

        settings = get_settings()
        engine = create_async_engine(settings.async_database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        apt_uuid = UUID(appointment_id)

        async with session_factory() as db:
            # Load appointment with relationships
            query = (
                select(Appointment)
                .options(
                    joinedload(Appointment.customer),
                    joinedload(Appointment.organization),
                    joinedload(Appointment.service_type),
                )
                .where(Appointment.id == apt_uuid)
            )

            result = await db.execute(query)
            appointment = result.scalar_one_or_none()

            if not appointment:
                logger.error(f"Appointment {appointment_id} not found")
                return {"success": False, "error": "Appointment not found"}

            if appointment.reminder_sent_at:
                logger.info(f"Reminder already sent for appointment {appointment_id}")
                return {"success": False, "error": "Reminder already sent"}

            # Get customer phone
            customer = appointment.customer
            organization = appointment.organization
            service_type = appointment.service_type

            if not customer or not customer.phone_number:
                logger.error(f"No customer phone for appointment {appointment_id}")
                return {"success": False, "error": "No customer phone"}

            # Format reminder message
            # Convert to org timezone for display
            import pytz
            org_tz = pytz.timezone(organization.timezone)
            local_time = appointment.scheduled_start.astimezone(org_tz)

            time_str = local_time.strftime("%I:%M %p").lower().lstrip("0")
            date_str = local_time.strftime("%A %d de %B")

            # Translate day and month to Spanish
            day_translations = {
                "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles",
                "Thursday": "jueves", "Friday": "viernes", "Saturday": "sábado", "Sunday": "domingo"
            }
            month_translations = {
                "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
                "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
                "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre"
            }

            for eng, esp in day_translations.items():
                date_str = date_str.replace(eng, esp)
            for eng, esp in month_translations.items():
                date_str = date_str.replace(eng, esp)

            service_name = service_type.name if service_type else "tu cita"
            message = (
                f"Hola! Te recordamos tu cita de {service_name} "
                f"mañana {date_str} a las {time_str} en {organization.name}. "
                f"Te esperamos!"
            )

            # Send via Twilio (or log in dev mode)
            if settings.twilio_account_sid and settings.twilio_auth_token:
                try:
                    from twilio.rest import Client

                    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

                    client.messages.create(
                        from_=settings.twilio_whatsapp_number,
                        body=message,
                        to=f"whatsapp:{customer.phone_number}",
                    )
                    logger.info(f"Sent reminder to {customer.phone_number}")
                except Exception as e:
                    logger.error(f"Failed to send reminder via Twilio: {e}")
                    return {"success": False, "error": str(e)}
            else:
                logger.info(f"[DEV] Would send reminder to {customer.phone_number}: {message}")

            # Mark reminder as sent
            appointment.reminder_sent_at = datetime.now(timezone.utc)
            await db.commit()

            return {"success": True, "phone": customer.phone_number}

        await engine.dispose()

    return asyncio.run(_send_reminder())
