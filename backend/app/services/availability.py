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

    # Blocked dates suppress recurring weekly rules only. A specific-date
    # event is an explicit "we *are* open for this on this day" override and
    # is intentionally honored even inside a blocked range — admins are warned
    # at the time they create either side, so a specific-date slot inside a
    # blocked range is a deliberate exception.
    blocked = await db.execute(
        select(BlockedDate).where(
            BlockedDate.tenant_id == tenant.id,
            BlockedDate.date_from <= target_date,
            BlockedDate.date_to >= target_date,
        )
    )
    is_blocked = blocked.scalar_one_or_none() is not None

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

    # Weekly rules — skipped on blocked dates.
    if not is_blocked:
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


async def materialize_slot_from_rule(
    db: AsyncSession,
    tenant: Tenant,
    rule_id: uuid_mod.UUID,
    target_date: date,
) -> SpecificDateSlot:
    """Promote one occurrence of a recurring AvailabilityRule into a
    real SpecificDateSlot row that campaigns / bookings / reviews can
    attach to.

    Idempotent: if a slot already exists for (rule_id, target_date)
    this returns it instead of creating a duplicate. The partial unique
    index `ux_specific_date_slots_rule_date` is the race-safety net —
    two admins clicking Start Campaign simultaneously will both end up
    pointing at the same row.

    Date is *frozen* on materialization (decision Phase A): later rule
    edits to start_time / end_time / services propagate to "safe" rows
    in Phase B, but the calendar date itself does not move — a
    materialized slot keeps its day even if the rule's day_of_week is
    later changed.

    Raises HTTPException-friendly ValueError if the rule isn't found,
    isn't active, or the date doesn't match its day_of_week (which
    would silently create a slot on a day the rule never ran on).
    """
    from sqlalchemy.exc import IntegrityError

    existing = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.availability_rule_id == rule_id,
            SpecificDateSlot.date == target_date,
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    rule = (await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id,
            AvailabilityRule.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if rule is None:
        raise ValueError(f"Availability rule {rule_id} not found")
    if not rule.is_active:
        raise ValueError(f"Availability rule {rule_id} is inactive")
    if rule.day_of_week != target_date.weekday():
        raise ValueError(
            f"Date {target_date} (weekday {target_date.weekday()}) does not "
            f"match rule's day_of_week ({rule.day_of_week})"
        )

    # Stamp the date onto the materialized slot's label so admins can tell
    # one occurrence from another in lists and campaign pickers — e.g.
    # "Thursday Gathering June 4, 2026" instead of N rows all labelled
    # "Thursday Gathering". On Windows %-d is unsupported, so fall back to
    # a stripped %d.
    base = rule.label or "Recurring event"
    try:
        date_str = target_date.strftime("%B %-d, %Y")
    except (ValueError, OSError):
        date_str = target_date.strftime("%B %d, %Y").replace(" 0", " ")
    materialized_label = f"{base} {date_str}"

    slot = SpecificDateSlot(
        tenant_id=tenant.id,
        date=target_date,
        label=materialized_label,
        location=rule.location,
        start_time=rule.start_time,
        end_time=rule.end_time,
        buffer_minutes=rule.buffer_minutes,
        service_config=rule.service_config,
        is_active=True,
        allow_roster_sharing=rule.allow_roster_sharing,
        availability_rule_id=rule.id,
    )
    db.add(slot)
    try:
        await db.flush()
    except IntegrityError:
        # Race: another request materialized the same (rule, date)
        # between our SELECT and INSERT. Roll back this attempt and
        # return the row the winner created.
        await db.rollback()
        winner = (await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == tenant.id,
                SpecificDateSlot.availability_rule_id == rule_id,
                SpecificDateSlot.date == target_date,
            )
        )).scalar_one()
        return winner
    return slot


# Fields the propagation engine considers when deciding whether the
# rule diverged from a materialized slot. Date is intentionally excluded
# — materialized slots have a frozen calendar date (Phase A decision).
# day_of_week is also excluded because changing it would change the
# weekday of the materialized slot, which would require moving the date
# — better handled as a manual admin decision.
_PROPAGATED_RULE_FIELDS = (
    "label",
    "location",
    "start_time",
    "end_time",
    "buffer_minutes",
    "service_config",
    "allow_roster_sharing",
)


def _format_rule_value(field: str, value):
    """Render a rule value for display in the drift summary."""
    if value is None:
        return None
    if field in ("start_time", "end_time"):
        try:
            return value.strftime("%H:%M")
        except AttributeError:
            return str(value)
    return value


async def _slot_is_safe_to_propagate(
    db: AsyncSession,
    slot: SpecificDateSlot,
) -> bool:
    """A materialized slot is "safe" for silent propagation when no
    bookings exist against it and no campaign is attached. Either
    condition flips the slot into "manual review" instead — pushing
    rule changes against a slot volunteers already RSVP'd to would
    silently change the deal under their feet.

    Note: ALL non-cancelled bookings count, including past ones, so
    historic bookings still protect a slot from drift propagation —
    the slot's own data has to stay faithful to what the volunteers
    showed up to.
    """
    from app.models.booking import Booking, BookingStatus
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
    )

    booking_count = (await db.execute(
        select(func.count()).where(
            Booking.event_slot_id == slot.id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )).scalar() or 0
    if booking_count > 0:
        return False

    # An active or awaiting-approval campaign is a live ask — don't
    # mutate the slot under it. Completed/cancelled campaigns no
    # longer constrain us.
    blocking_campaign = (await db.execute(
        select(RecruitmentCampaign.id).where(
            RecruitmentCampaign.event_slot_id == slot.id,
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.ACTIVE,
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.DRAFT,
                    CampaignStatus.PAUSED,
                ]
            ),
        ).limit(1)
    )).scalar_one_or_none()
    return blocking_campaign is None


def _compute_rule_diff(rule: AvailabilityRule, slot: SpecificDateSlot) -> list[dict]:
    """Return the human-readable diff between a rule's current values
    and a materialized slot's current values. Empty list means the
    slot is already in sync."""
    diff: list[dict] = []
    for field in _PROPAGATED_RULE_FIELDS:
        rule_val = getattr(rule, field, None)
        slot_val = getattr(slot, field, None)
        if rule_val == slot_val:
            continue
        diff.append({
            "field": field,
            "from": _format_rule_value(field, slot_val),
            "to": _format_rule_value(field, rule_val),
        })
    return diff


async def cleanup_unused_materialized_slots(
    db: AsyncSession,
    tenant: Tenant,
    rule_id: uuid_mod.UUID,
) -> int:
    """When a rule is about to be deleted, scrub the materialized
    slots that have no bookings AND no campaigns — they exist only
    as derivatives of the rule, and once the rule is gone they'd
    sit as orphan "(unnamed)" rows on the calendar with their FK
    nulled by ON DELETE SET NULL.

    Slots that DO have any non-cancelled booking, or any campaign
    attached (regardless of status — completed campaigns are
    historical record), are kept; their FK nulls out and they
    survive as standalone specific events because the real state
    that lived on them is worth preserving.

    Returns the count of slots deleted. Call BEFORE the rule
    deletion so the FK still resolves while we iterate.
    """
    from app.models.booking import Booking, BookingStatus
    from app.models.recruitment_campaign import RecruitmentCampaign

    candidates = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.availability_rule_id == rule_id,
        )
    )).scalars().all()

    deleted = 0
    for slot in candidates:
        booking_count = (await db.execute(
            select(func.count()).where(
                Booking.event_slot_id == slot.id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )).scalar() or 0
        if booking_count > 0:
            continue
        campaign_count = (await db.execute(
            select(func.count()).where(
                RecruitmentCampaign.event_slot_id == slot.id,
            )
        )).scalar() or 0
        if campaign_count > 0:
            continue
        await db.delete(slot)
        deleted += 1
    if deleted:
        await db.flush()
    return deleted


async def propagate_rule_edit_to_materialized_slots(
    db: AsyncSession,
    tenant: Tenant,
    rule: AvailabilityRule,
) -> dict:
    """Fan out a rule edit to every SpecificDateSlot materialized from
    this rule that hasn't happened yet.

    For each candidate slot:
      - If it's "safe" (no bookings, no active campaign) → overwrite
        the propagated fields with the rule's new values silently.
      - Otherwise → stash the diff on the slot
        (rule_drift_at + rule_drift_summary). The dashboard surfaces
        these as alerts and the admin chooses accept / ignore.

    Returns a summary dict for logging:
      {"propagated": N, "drifted": M, "unchanged": K}
    """
    from datetime import datetime as _datetime, timezone as _timezone

    today = date.today()
    materialized = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.availability_rule_id == rule.id,
            SpecificDateSlot.date >= today,
            SpecificDateSlot.is_active.is_(True),
        )
    )).scalars().all()

    propagated = 0
    drifted = 0
    unchanged = 0

    for slot in materialized:
        diff = _compute_rule_diff(rule, slot)
        if not diff:
            unchanged += 1
            continue

        if await _slot_is_safe_to_propagate(db, slot):
            for field in _PROPAGATED_RULE_FIELDS:
                setattr(slot, field, getattr(rule, field))
            # If a prior drift was sitting unresolved, clear it — the
            # admin's edit superseded whatever was queued.
            slot.rule_drift_at = None
            slot.rule_drift_summary = None
            propagated += 1
        else:
            slot.rule_drift_at = _datetime.now(_timezone.utc)
            slot.rule_drift_summary = diff
            drifted += 1

    await db.flush()
    return {"propagated": propagated, "drifted": drifted, "unchanged": unchanged}


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
