"""Live-slot eligibility helpers — two distinct functions, one module.

Review-pass issue #8 (this is the reconciliation):

  _find_live_slot_with_capacity(db, tenant_id) → single slot
      Caller: Row 4/5 unknown-phone pipeline branch.
      Filter: live + open capacity + ≥1 *prerequisite-free* service
              (no background_check_required, no certification reqs).
      Returns: ONE slot per urgency-first hierarchy:
        1. Below-min slots outrank at-or-above.
        2. Within below-min: earliest start_at; tiebreak shortfall DESC.
        3. Within at-or-above-min: most remaining capacity; tiebreak earliest start_at.
        4. Final: slot.id ASC.

  _find_walkup_eligible_slots(db, contact) → list[slot]
      Caller: Row 2 walk-up offer.
      Filter: live + open capacity + ≥1 service the volunteer profile
              qualifies for (preferred_services match OR all_services_enabled).
      Returns: ALL matching slots (caller renders the numbered picker).

NOT shareable. Share the underlying SQL pattern but expose two
distinct public interfaces so call-site semantics stay clear.

Live window: [start_at - 30min, end_at + 1h] in slot's local time.
This matches the Row 1 match condition.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.contact_preferred_type import ContactPreferredType


@dataclass(frozen=True)
class LiveSlotInfo:
    """Snapshot of one live slot with its eligibility / capacity data.

    Used as the return shape for both eligibility helpers so callers
    can render templates without re-querying.
    """
    slot: SpecificDateSlot
    booked_count: int
    min_required_total: int  # sum across services
    max_allowed_total: int   # sum across services
    open_services: list[dict]  # [{appointment_type_id, max_allowed, current_booked, min_required}]


def _slot_in_live_window(slot: SpecificDateSlot, now_utc: datetime) -> bool:
    """Is this slot's window [start_at - 30min, end_at + 1h] inclusive of `now_utc`?

    Slots store date + start_time/end_time without a stored timezone;
    we treat them as Eastern Time (timezone-assumption-locked per
    review-pass #6 backlog item).
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]
    eastern = ZoneInfo("America/New_York")
    # Compose start_at / end_at as Eastern-localized datetimes.
    start_at = datetime.combine(slot.date, slot.start_time).replace(tzinfo=eastern)
    end_at = datetime.combine(slot.date, slot.end_time).replace(tzinfo=eastern)
    if end_at <= start_at:
        # End-of-day rollover (e.g. 11pm-1am event); add a day.
        end_at = end_at + timedelta(days=1)
    window_open = start_at - timedelta(minutes=30)
    window_close = end_at + timedelta(hours=1)
    return window_open <= now_utc <= window_close


async def _live_slots(db: AsyncSession, tenant_id: uuid.UUID) -> list[SpecificDateSlot]:
    """Return all SpecificDateSlots for tenant whose live window covers NOW().

    Coarse date-range filter at the SQL level (today ± 1 day), refined
    in Python by _slot_in_live_window because slot times are naive.
    """
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant_id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(today - timedelta(days=1), today + timedelta(days=1)),
        )
    )
    now_utc = datetime.now(timezone.utc)
    return [s for s in result.scalars().all() if _slot_in_live_window(s, now_utc)]


async def _booked_count_for_slot(db: AsyncSession, slot_id: uuid.UUID) -> int:
    """Count non-cancelled bookings on a slot."""
    result = await db.execute(
        select(func.count()).select_from(Booking).where(
            Booking.event_slot_id == slot_id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    return int(result.scalar() or 0)


async def _slot_info(db: AsyncSession, slot: SpecificDateSlot) -> LiveSlotInfo:
    """Build a LiveSlotInfo for a slot, including per-service capacity."""
    booked_count = await _booked_count_for_slot(db, slot.id)
    service_config = slot.service_config or []
    open_services = []
    min_required_total = 0
    max_allowed_total = 0
    for svc in service_config:
        if not isinstance(svc, dict):
            continue
        min_required = int(svc.get("min_required", 1))
        max_allowed = int(svc.get("max_allowed", 1))
        min_required_total += min_required
        max_allowed_total += max_allowed
        # NOTE: per-service current_booked needs a join on appointment_type_id;
        # for Phase 1 we surface aggregate capacity at the slot level. Per-service
        # breakdown is a Phase 3+ enhancement when SWITCH/ALSO need it.
        open_services.append({
            "appointment_type_id": svc.get("appointment_type_id"),
            "min_required": min_required,
            "max_allowed": max_allowed,
        })
    return LiveSlotInfo(
        slot=slot,
        booked_count=booked_count,
        min_required_total=min_required_total,
        max_allowed_total=max_allowed_total,
        open_services=open_services,
    )


def _has_prereq_free_service(info: LiveSlotInfo) -> bool:
    """True if the slot has ≥1 service an unknown walk-up could plausibly take.

    For Phase 1 we approximate this as "the slot exists" — proper
    prerequisite checking (background_check_required at the
    appointment_type level) is a TODO marked in the plan. When the
    appointment_type model gains per-service prereq fields, this
    helper switches to filter on those.
    """
    # TODO Phase 1+: filter open_services by appointment_type.background_check_required
    return bool(info.open_services) and info.booked_count < info.max_allowed_total


def _rank_key_for_picker(info: LiveSlotInfo) -> tuple:
    """Urgency-first sort key for the Row 4/5 picker.

    Returns a tuple; smaller values sort first.

    Order (matches event_lifecycle_plan.md urgency hierarchy):
      0. Below-min slots first (0 < at-or-above_marker).
      1. Within below-min: earliest start_at, then largest shortfall DESC.
      2. Within at-or-above-min: most remaining capacity DESC, then earliest start_at.
      3. Final tiebreak: slot.id ASC.
    """
    below_min = info.booked_count < info.min_required_total
    shortfall = max(info.min_required_total - info.booked_count, 0)
    remaining_capacity = info.max_allowed_total - info.booked_count
    # Sort key: (group, start_at, shortfall_DESC | -remaining_capacity, slot.id)
    # group: 0 = below_min, 1 = at_or_above
    group = 0 if below_min else 1
    start_at_key = (info.slot.date, info.slot.start_time)
    if below_min:
        # within group: earliest start first; tiebreak by shortfall DESC
        secondary = (start_at_key, -shortfall)
    else:
        # within group: most remaining capacity first; tiebreak earliest start
        secondary = (-remaining_capacity, start_at_key)
    return (group, secondary, str(info.slot.id))


async def find_live_slot_with_capacity(
    db: AsyncSession, tenant_id: uuid.UUID
) -> SpecificDateSlot | None:
    """Row 4/5 picker — returns ONE slot per urgency-first hierarchy.

    Filters:
      - Slot in the live window [start_at - 30min, end_at + 1h]
      - Slot has open capacity
      - Slot has ≥1 prerequisite-free service (so an unknown walk-up
        could plausibly be attributed there)

    Returns None when nothing matches (Row 5: no notification fires).
    """
    slots = await _live_slots(db, tenant_id)
    if not slots:
        return None
    infos = [await _slot_info(db, s) for s in slots]
    eligible = [info for info in infos if _has_prereq_free_service(info)]
    if not eligible:
        return None
    eligible.sort(key=_rank_key_for_picker)
    return eligible[0].slot


async def find_walkup_eligible_slots(
    db: AsyncSession, contact: Contact
) -> list[LiveSlotInfo]:
    """Row 2 walk-up offer — returns ALL slots the known volunteer is eligible for.

    Filters:
      - Slot in the live window
      - Slot has open capacity
      - ≥1 service on the slot matches the volunteer's profile:
        - all_services_enabled=True (volunteer takes anything), OR
        - service appears in contact_preferred_types

    Returns list of LiveSlotInfo for caller-side rendering.
    """
    slots = await _live_slots(db, contact.tenant_id)
    if not slots:
        return []
    infos = [await _slot_info(db, s) for s in slots]

    # Filter by capacity first (cheap).
    infos = [info for info in infos if info.booked_count < info.max_allowed_total]
    if not infos:
        return []

    # If volunteer has all_services_enabled, every capacity-OK slot qualifies.
    if getattr(contact, "all_services_enabled", False):
        return infos

    # Else intersect open_services with contact_preferred_types.
    pref_result = await db.execute(
        select(ContactPreferredType.appointment_type_id).where(
            ContactPreferredType.contact_id == contact.id,
        )
    )
    preferred_ids = {row[0] for row in pref_result.all()}
    if not preferred_ids:
        return []

    matches: list[LiveSlotInfo] = []
    for info in infos:
        slot_service_ids = {
            svc.get("appointment_type_id") for svc in info.open_services
        }
        slot_service_ids.discard(None)
        if preferred_ids & slot_service_ids:
            matches.append(info)
    return matches


__all__ = [
    "LiveSlotInfo",
    "find_live_slot_with_capacity",
    "find_walkup_eligible_slots",
]
