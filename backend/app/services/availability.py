"""Slot computation engine for volunteer/non-profit scheduling.

Each availability window (weekly rule or specific date event) defines:
- When it runs (day/date, start, end)
- Which services are needed, with min_required and max_allowed per service

Example: Monday 9am-12pm needs "Kitchen Help" (min 3, max 6) and "Front Desk" (min 1, max 2).

Slots are generated using each service's duration_minutes.
A slot shows as available if current bookings < max_allowed.
A slot shows "needs X more" if current bookings < min_required.
"""

import uuid as uuid_mod
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule, SpecificDateSlot
from app.models.blocked_date import BlockedDate
from app.models.booking import Booking, BookingStatus
from app.models.tenant import Tenant
from app.services.calendar import get_busy_periods

logger = get_logger("availability")


def _get_service_limits(service_config: list | None, appointment_type_id: str) -> tuple[int, int] | None:
    """Get (min_required, max_allowed) for a service from the config.

    Returns None if the service is not in this window's config.
    Returns (1, 1) as default if config is NULL (all services, no min).
    """
    if not service_config:
        return (1, 1)

    appt_str = str(appointment_type_id)
    for entry in service_config:
        if str(entry.get("appointment_type_id", "")) == appt_str:
            return (
                entry.get("min_required", 1),
                entry.get("max_allowed", entry.get("min_required", 1)),
            )
    return None  # Service not configured for this window


async def compute_available_slots(
    db: AsyncSession,
    target_date: date,
    appointment_type_id: str,
    tenant: Tenant,
    max_slots: int = 0,
) -> list[dict]:
    """Compute available slots for a service on a date.

    Returns slots with capacity info:
      {"start": datetime, "end": datetime, "booked": int, "min_required": int, "max_allowed": int}
    """
    import pytz
    tz = pytz.timezone(tenant.business_timezone)

    # Check blocked dates
    blocked = await db.execute(
        select(BlockedDate).where(
            BlockedDate.tenant_id == tenant.id,
            BlockedDate.date_from <= target_date,
            BlockedDate.date_to >= target_date,
        )
    )
    if blocked.scalar_one_or_none():
        return []

    # Load appointment type
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        return []

    duration = timedelta(minutes=appt_type.duration_minutes)

    # Collect windows: (start_dt, end_dt, buffer, min_required, max_allowed)
    windows = []

    # Weekly rules
    day_of_week = target_date.weekday()
    rules_result = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.day_of_week == day_of_week,
            AvailabilityRule.is_active.is_(True),
        )
    )
    for rule in rules_result.scalars().all():
        limits = _get_service_limits(rule.service_config, appointment_type_id)
        if limits is None:
            continue
        min_req, max_allow = limits
        start_dt = tz.localize(datetime.combine(target_date, rule.start_time))
        end_dt = tz.localize(datetime.combine(target_date, rule.end_time))
        buffer = timedelta(minutes=rule.buffer_minutes)
        windows.append((start_dt, end_dt, buffer, min_req, max_allow))

    # Specific date slots
    specific_result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.date == target_date,
            SpecificDateSlot.is_active.is_(True),
        )
    )
    for sds in specific_result.scalars().all():
        limits = _get_service_limits(sds.service_config, appointment_type_id)
        if limits is None:
            continue
        min_req, max_allow = limits
        start_dt = tz.localize(datetime.combine(target_date, sds.start_time))
        end_dt = tz.localize(datetime.combine(target_date, sds.end_time))
        buffer = timedelta(minutes=sds.buffer_minutes)
        windows.append((start_dt, end_dt, buffer, min_req, max_allow))

    if not windows:
        return []

    # Google Calendar busy periods
    day_start = tz.localize(datetime.combine(target_date, time.min))
    day_end = tz.localize(datetime.combine(target_date, time.max))

    try:
        busy_periods = await get_busy_periods(day_start, day_end, tenant=tenant)
    except Exception:
        logger.warning("Google Calendar unavailable, assuming no busy periods")
        busy_periods = []

    busy_ranges = [
        (datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]))
        for p in busy_periods
    ]

    # Existing bookings of this type on this date
    appt_uuid = uuid_mod.UUID(str(appointment_type_id))
    active_statuses = [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED, BookingStatus.COMPLETED]
    bookings_result = await db.execute(
        select(Booking).where(
            Booking.tenant_id == tenant.id,
            Booking.appointment_type_id == appt_uuid,
            Booking.scheduled_at >= day_start,
            Booking.scheduled_at <= day_end,
            Booking.status.in_(active_statuses),
        )
    )
    existing_bookings = [
        (b.scheduled_at, b.scheduled_at + duration)
        for b in bookings_result.scalars().all()
    ]

    # Generate slots
    slots = []
    for window_start, window_end, buffer, min_required, max_allowed in windows:
        cursor = window_start

        while cursor + duration <= window_end:
            slot_start = cursor
            slot_end = cursor + duration

            # Skip if Google Calendar busy
            is_busy = False
            for busy_start, busy_end in busy_ranges:
                if slot_start < (busy_end + buffer) and slot_end > (busy_start - buffer):
                    is_busy = True
                    cursor = busy_end + buffer
                    break
            if is_busy:
                continue

            # Count existing bookings overlapping this slot
            booked = sum(1 for (bs, be) in existing_bookings if slot_start < be and slot_end > bs)

            if booked < max_allowed:
                slots.append({
                    "start": slot_start,
                    "end": slot_end,
                    "booked": booked,
                    "min_required": min_required,
                    "max_allowed": max_allowed,
                })
                if max_slots and len(slots) >= max_slots:
                    return slots

            cursor += duration + buffer

    return slots


async def count_bookings_at_slot(
    db: AsyncSession,
    tenant_id,
    appointment_type_id: str,
    scheduled_at: datetime,
    duration_minutes: int,
) -> int:
    """Count active bookings of the same type overlapping a slot."""
    slot_end = scheduled_at + timedelta(minutes=duration_minutes)
    appt_uuid = uuid_mod.UUID(str(appointment_type_id))
    active_statuses = [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]

    result = await db.execute(
        select(func.count()).select_from(Booking).where(
            Booking.tenant_id == tenant_id,
            Booking.appointment_type_id == appt_uuid,
            Booking.status.in_(active_statuses),
            Booking.scheduled_at < slot_end,
            (Booking.scheduled_at + func.make_interval(0, 0, 0, 0, 0, duration_minutes)) > scheduled_at,
        )
    )
    return result.scalar() or 0


async def get_service_limits_for_booking(
    db: AsyncSession,
    tenant: Tenant,
    appointment_type_id: str,
    scheduled_at: datetime,
) -> tuple[int, int]:
    """Get (min_required, max_allowed) for a service at a given time.

    Returns (0, 0) if the service is not available at this time.
    """
    import pytz
    tz = pytz.timezone(tenant.business_timezone)
    local_dt = scheduled_at.astimezone(tz)
    slot_time = local_dt.time()
    slot_date = local_dt.date()
    day_of_week = local_dt.weekday()

    # Load appointment type for duration
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        return (0, 0)

    slot_end_time = (datetime.combine(slot_date, slot_time) + timedelta(minutes=appt_type.duration_minutes)).time()

    best = (0, 0)

    # Check weekly rules
    rules_result = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.day_of_week == day_of_week,
            AvailabilityRule.is_active.is_(True),
            AvailabilityRule.start_time <= slot_time,
            AvailabilityRule.end_time >= slot_end_time,
        )
    )
    for rule in rules_result.scalars().all():
        limits = _get_service_limits(rule.service_config, appointment_type_id)
        if limits and limits[1] > best[1]:
            best = limits

    # Check specific date slots
    specific_result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.date == slot_date,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.start_time <= slot_time,
            SpecificDateSlot.end_time >= slot_end_time,
        )
    )
    for sds in specific_result.scalars().all():
        limits = _get_service_limits(sds.service_config, appointment_type_id)
        if limits and limits[1] > best[1]:
            best = limits

    return best
