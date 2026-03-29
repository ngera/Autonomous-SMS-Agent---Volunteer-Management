"""Slot computation engine.

Computes available appointment slots by:
1. Loading working hours (availability_rules) for the requested date
2. Querying Google Calendar freeBusy for busy periods
3. Checking blocked dates
4. Subtracting busy periods + buffer from working hours
5. Returning gaps that fit the requested appointment duration
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule
from app.models.blocked_date import BlockedDate
from app.models.booking import Booking, BookingStatus
from app.models.tenant import Tenant
from app.services.calendar import get_busy_periods

logger = get_logger("availability")


async def compute_available_slots(
    db: AsyncSession,
    target_date: date,
    appointment_type_id: str,
    tenant: Tenant,
    max_slots: int = 0,
) -> list[dict]:
    """Compute available time slots for a given date and appointment type.

    Returns up to max_slots available slots as [{"start": datetime, "end": datetime}].
    """
    import pytz

    tz = pytz.timezone(tenant.business_timezone)

    # Check if date is blocked
    blocked = await db.execute(
        select(BlockedDate).where(
            BlockedDate.tenant_id == tenant.id,
            BlockedDate.date_from <= target_date,
            BlockedDate.date_to >= target_date,
        )
    )
    if blocked.scalar_one_or_none():
        return []

    # Get working hours for this day of week (0=Monday)
    day_of_week = target_date.weekday()
    rules_result = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.day_of_week == day_of_week,
            AvailabilityRule.is_active.is_(True),
        )
    )
    rules = rules_result.scalars().all()
    if not rules:
        return []

    # Get appointment type duration
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        return []

    duration = timedelta(minutes=appt_type.duration_minutes)

    # Build working hour windows
    working_windows = []
    for rule in rules:
        start_dt = tz.localize(datetime.combine(target_date, rule.start_time))
        end_dt = tz.localize(datetime.combine(target_date, rule.end_time))
        buffer = timedelta(minutes=rule.buffer_minutes)
        slot_step = timedelta(minutes=rule.slot_duration_minutes)
        working_windows.append((start_dt, end_dt, buffer, slot_step))

    if not working_windows:
        return []

    # Get busy periods from Google Calendar
    day_start = tz.localize(datetime.combine(target_date, time.min))
    day_end = tz.localize(datetime.combine(target_date, time.max))

    try:
        busy_periods = await get_busy_periods(day_start, day_end, tenant=tenant)
    except Exception:
        logger.warning("Failed to fetch busy periods from Google Calendar, assuming none")
        busy_periods = []

    # Parse busy periods
    busy_ranges = []
    for period in busy_periods:
        busy_start = datetime.fromisoformat(period["start"])
        busy_end = datetime.fromisoformat(period["end"])
        busy_ranges.append((busy_start, busy_end))

    # Get existing bookings for this date (exclude cancelled)
    active_statuses = [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED, BookingStatus.COMPLETED]
    bookings_result = await db.execute(
        select(Booking, AppointmentType.duration_minutes)
        .join(AppointmentType, Booking.appointment_type_id == AppointmentType.id)
        .where(
            Booking.tenant_id == tenant.id,
            Booking.scheduled_at >= day_start,
            Booking.scheduled_at <= day_end,
            Booking.status.in_(active_statuses),
        )
    )
    for booking, dur_minutes in bookings_result.all():
        busy_ranges.append((
            booking.scheduled_at,
            booking.scheduled_at + timedelta(minutes=dur_minutes),
        ))

    # Compute available slots
    # Use the larger of slot_step and duration to avoid overlapping slots
    slots = []
    for window_start, window_end, buffer, slot_step in working_windows:
        effective_step = max(slot_step, duration)
        cursor = window_start

        while cursor + duration <= window_end:
            slot_end = cursor + duration

            # Check overlap with busy periods (including buffer)
            is_busy = False
            for busy_start, busy_end in busy_ranges:
                buffered_busy_start = busy_start - buffer
                buffered_busy_end = busy_end + buffer
                if cursor < buffered_busy_end and slot_end > buffered_busy_start:
                    is_busy = True
                    # Jump past this busy period
                    cursor = busy_end + buffer
                    # Align to next slot step boundary
                    elapsed = (cursor - window_start).total_seconds()
                    step_secs = slot_step.total_seconds()
                    if step_secs > 0 and elapsed % step_secs != 0:
                        cursor = window_start + timedelta(
                            seconds=((elapsed // step_secs) + 1) * step_secs
                        )
                    break

            if not is_busy:
                slots.append({"start": cursor, "end": slot_end})
                cursor += effective_step

                if max_slots and len(slots) >= max_slots:
                    return slots

    return slots
