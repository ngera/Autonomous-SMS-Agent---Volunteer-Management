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

from app.core.config import settings
from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule
from app.models.blocked_date import BlockedDate
from app.services.calendar import get_busy_periods

logger = get_logger("availability")


async def compute_available_slots(
    db: AsyncSession,
    target_date: date,
    appointment_type_id: str,
    max_slots: int = 3,
) -> list[dict]:
    """Compute available time slots for a given date and appointment type.

    Returns up to max_slots available slots as [{"start": datetime, "end": datetime}].
    """
    import pytz

    tz = pytz.timezone(settings.business_timezone)

    # Check if date is blocked
    blocked = await db.execute(
        select(BlockedDate).where(
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
        working_windows.append((start_dt, end_dt, buffer))

    if not working_windows:
        return []

    # Get busy periods from Google Calendar
    day_start = tz.localize(datetime.combine(target_date, time.min))
    day_end = tz.localize(datetime.combine(target_date, time.max))

    try:
        busy_periods = await get_busy_periods(day_start, day_end)
    except Exception:
        logger.warning("Failed to fetch busy periods, returning no slots")
        return []

    # Parse busy periods
    busy_ranges = []
    for period in busy_periods:
        busy_start = datetime.fromisoformat(period["start"])
        busy_end = datetime.fromisoformat(period["end"])
        busy_ranges.append((busy_start, busy_end))

    # Compute available slots
    slots = []
    for window_start, window_end, buffer in working_windows:
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
                    break

            if not is_busy:
                slots.append({"start": cursor, "end": slot_end})
                cursor = slot_end + buffer

                if len(slots) >= max_slots:
                    return slots

    return slots
