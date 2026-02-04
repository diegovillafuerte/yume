"""Scheduling service - availability calculation and appointment management."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tracing import traced
from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Availability,
    AvailabilityType,
    ServiceType,
    Staff,
)
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.schemas.availability import AvailableSlot


async def get_appointment(db: AsyncSession, appointment_id: UUID) -> Appointment | None:
    """Get appointment by ID."""
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    return result.scalar_one_or_none()


async def list_appointments(
    db: AsyncSession,
    organization_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    customer_id: UUID | None = None,
    staff_id: UUID | None = None,
) -> list[Appointment]:
    """List appointments with optional filters."""
    query = select(Appointment).where(Appointment.organization_id == organization_id)

    if start_date:
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_start >= start_dt)

    if end_date:
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_start <= end_dt)

    if customer_id:
        query = query.where(Appointment.customer_id == customer_id)

    if staff_id:
        query = query.where(Appointment.staff_id == staff_id)

    result = await db.execute(query.order_by(Appointment.scheduled_start))
    return list(result.scalars().all())


@traced
async def create_appointment(
    db: AsyncSession, organization_id: UUID, appointment_data: AppointmentCreate
) -> Appointment:
    """Create a new appointment."""
    appointment = Appointment(
        organization_id=organization_id,
        location_id=appointment_data.location_id,
        customer_id=appointment_data.customer_id,
        staff_id=appointment_data.staff_id,
        service_type_id=appointment_data.service_type_id,
        scheduled_start=appointment_data.scheduled_start,
        scheduled_end=appointment_data.scheduled_end,
        source=appointment_data.source,
        status=AppointmentStatus.PENDING.value,
        notes=appointment_data.notes,
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)
    return appointment


async def update_appointment(
    db: AsyncSession, appointment: Appointment, appointment_data: AppointmentUpdate
) -> Appointment:
    """Update an appointment."""
    update_dict = appointment_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(appointment, key, value)
    await db.flush()
    await db.refresh(appointment)
    return appointment


async def cancel_appointment(
    db: AsyncSession, appointment: Appointment, reason: str | None = None
) -> Appointment:
    """Cancel an appointment."""
    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancellation_reason = reason
    await db.flush()
    await db.refresh(appointment)
    return appointment


async def complete_appointment(
    db: AsyncSession, appointment: Appointment, notes: str | None = None
) -> Appointment:
    """Mark appointment as completed."""
    appointment.status = AppointmentStatus.COMPLETED.value
    if notes:
        appointment.notes = notes
    await db.flush()
    await db.refresh(appointment)
    return appointment


async def check_appointment_conflicts(
    db: AsyncSession,
    organization_id: UUID,
    staff_id: UUID | None,
    spot_id: UUID | None,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: UUID | None = None,
) -> list[Appointment]:
    """Check for conflicting appointments.

    Returns a list of appointments that conflict with the proposed time slot.
    An appointment conflicts if:
    - It's for the same staff member and times overlap
    - It's for the same spot and times overlap
    - It's in PENDING or CONFIRMED status (not cancelled/completed)

    Args:
        db: Database session
        organization_id: Organization to check within
        staff_id: Staff member ID (optional, checks staff conflicts if provided)
        spot_id: Spot ID (optional, checks spot conflicts if provided)
        start_time: Proposed appointment start time
        end_time: Proposed appointment end time
        exclude_appointment_id: Appointment ID to exclude (for reschedule operations)

    Returns:
        List of conflicting appointments (empty if no conflicts)
    """
    if not staff_id and not spot_id:
        # Nothing to check conflicts against
        return []

    # Build overlap condition - three cases:
    # 1. Existing appointment starts during proposed slot
    # 2. Existing appointment ends during proposed slot
    # 3. Existing appointment completely contains proposed slot
    overlap_condition = or_(
        # Existing starts during proposed
        and_(
            Appointment.scheduled_start >= start_time,
            Appointment.scheduled_start < end_time,
        ),
        # Existing ends during proposed
        and_(
            Appointment.scheduled_end > start_time,
            Appointment.scheduled_end <= end_time,
        ),
        # Existing contains proposed
        and_(
            Appointment.scheduled_start <= start_time,
            Appointment.scheduled_end >= end_time,
        ),
    )

    # Build resource conflict conditions (staff OR spot)
    resource_conditions = []
    if staff_id:
        resource_conditions.append(Appointment.staff_id == staff_id)
    if spot_id:
        resource_conditions.append(Appointment.spot_id == spot_id)

    # Base query
    query = select(Appointment).where(
        Appointment.organization_id == organization_id,
        Appointment.status.in_([
            AppointmentStatus.PENDING.value,
            AppointmentStatus.CONFIRMED.value,
        ]),
        overlap_condition,
        or_(*resource_conditions),  # Staff OR spot conflict
    )

    # Exclude specific appointment (for reschedule)
    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)

    result = await db.execute(query)
    return list(result.scalars().all())


@traced
async def get_available_slots(
    db: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    service_type_id: UUID,
    date_from: date,
    date_to: date | None = None,
    staff_id: UUID | None = None,
    slot_interval_minutes: int = 30,
) -> list[AvailableSlot]:
    """Calculate available appointment slots.

    This is THE core scheduling algorithm. It:
    1. Gets the service duration
    2. Finds available staff (or specific staff if requested)
    3. For each staff member, finds their recurring availability
    4. Applies exceptions (blocked time, time off)
    5. Removes already-booked appointment slots
    6. Returns list of available time slots
    """
    if date_to is None:
        date_to = date_from

    # Get service type to know duration
    service_result = await db.execute(
        select(ServiceType).where(ServiceType.id == service_type_id)
    )
    service = service_result.scalar_one_or_none()
    if not service:
        return []

    duration_minutes = service.duration_minutes

    # Get staff members
    staff_query = select(Staff).where(
        Staff.organization_id == organization_id,
        Staff.is_active == True,
    )
    if staff_id:
        staff_query = staff_query.where(Staff.id == staff_id)

    staff_result = await db.execute(staff_query)
    staff_members = list(staff_result.scalars().all())

    if not staff_members:
        return []

    available_slots: list[AvailableSlot] = []

    # Iterate through each day in the range
    current_date = date_from
    while current_date <= date_to:
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday

        # For each staff member
        for staff_member in staff_members:
            # Get recurring availability for this day of week
            availability_result = await db.execute(
                select(Availability).where(
                    Availability.staff_id == staff_member.id,
                    Availability.type == AvailabilityType.RECURRING.value,
                    Availability.day_of_week == day_of_week,
                )
            )
            recurring_slots = list(availability_result.scalars().all())

            # Get exceptions for this specific date
            exception_result = await db.execute(
                select(Availability).where(
                    Availability.staff_id == staff_member.id,
                    Availability.type == AvailabilityType.EXCEPTION.value,
                    Availability.exception_date == current_date,
                )
            )
            exception = exception_result.scalar_one_or_none()

            # If there's an exception that marks the day as unavailable, skip this day
            if exception and not exception.is_available:
                continue

            # Use exception times if available, otherwise use recurring
            if exception and exception.is_available:
                time_slots = [(exception.start_time, exception.end_time)]
            else:
                time_slots = [(slot.start_time, slot.end_time) for slot in recurring_slots]

            # For each time slot, generate possible appointment times
            for start_time, end_time in time_slots:
                if not start_time or not end_time:
                    continue

                # Generate slots at intervals
                current_time = start_time
                while True:
                    # Calculate end time for this slot
                    slot_start_dt = datetime.combine(current_date, current_time, tzinfo=timezone.utc)
                    slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutes)

                    # Check if slot fits within available time
                    slot_end_time = slot_end_dt.time()
                    if slot_end_time > end_time:
                        break

                    # Check if slot conflicts with existing appointments
                    conflict_result = await db.execute(
                        select(Appointment).where(
                            Appointment.staff_id == staff_member.id,
                            Appointment.status.in_(
                                [
                                    AppointmentStatus.PENDING.value,
                                    AppointmentStatus.CONFIRMED.value,
                                ]
                            ),
                            or_(
                                # Appointment starts during this slot
                                and_(
                                    Appointment.scheduled_start >= slot_start_dt,
                                    Appointment.scheduled_start < slot_end_dt,
                                ),
                                # Appointment ends during this slot
                                and_(
                                    Appointment.scheduled_end > slot_start_dt,
                                    Appointment.scheduled_end <= slot_end_dt,
                                ),
                                # Appointment completely contains this slot
                                and_(
                                    Appointment.scheduled_start <= slot_start_dt,
                                    Appointment.scheduled_end >= slot_end_dt,
                                ),
                            ),
                        )
                    )
                    has_conflict = conflict_result.scalar_one_or_none() is not None

                    if not has_conflict:
                        available_slots.append(
                            AvailableSlot(
                                start_time=slot_start_dt,
                                end_time=slot_end_dt,
                                staff_id=staff_member.id,
                                staff_name=staff_member.name,
                            )
                        )

                    # Move to next slot
                    next_dt = slot_start_dt + timedelta(minutes=slot_interval_minutes)
                    current_time = next_dt.time()

        current_date += timedelta(days=1)

    return available_slots
