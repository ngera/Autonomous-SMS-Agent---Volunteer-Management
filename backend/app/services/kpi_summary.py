"""Tenant-level KPI snapshot used by the daily SMS digest and the
"summary" on-demand admin intent.

Two horizons mirror the dashboard tabs:
  - immediate    : T+0 → T+14  (Needs-You-Now tab)
  - planning     : T+15 → T+60 (Planning tab)

For each horizon we compute:
  - events_count
  - recurring vs specific split
  - total minimum staffing required
  - open_min (slots still below minimum)
  - at_risk events (count where booked < min_required)
  - campaigns_running (events with a non-terminal campaign)

Shared with:
  - app.scheduler.jobs.kpi_summary_tick (daily SMS)
  - app.agents.orchestrator.dashboard_summary_intent (on-demand recall)
  - (future) /api/v1/dashboard/kpi-summary if a JSON endpoint is wanted

Recurring-event materialization, booking aggregation, and campaign
classification all mirror the rules in
[app/api/dashboard.py](backend/app/api/dashboard.py) so the SMS and
the dashboard tell the same story.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import AvailabilityRule, SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
)
from app.models.tenant import Tenant


# Any campaign not in a terminal state counts as "running" — matches
# the dashboard KPI logic.
_TERMINAL_CAMPAIGN_STATUSES = {
    CampaignStatus.COMPLETED,
    CampaignStatus.CANCELLED,
    CampaignStatus.FAILED,
}


@dataclass
class HorizonStats:
    events_count: int = 0
    recurring_count: int = 0
    specific_count: int = 0
    total_required: int = 0
    open_min: int = 0
    at_risk: int = 0
    campaigns_running: int = 0


@dataclass
class KpiSummary:
    """Snapshot of the two horizons used in the SMS digest + recall."""
    tenant_name: str
    as_of: datetime
    immediate: HorizonStats = field(default_factory=HorizonStats)
    planning: HorizonStats = field(default_factory=HorizonStats)


async def _aggregate_horizon(
    db: AsyncSession,
    tenant: Tenant,
    window_start: date,
    window_end: date,
) -> HorizonStats:
    """Build a HorizonStats by walking specific slots + recurring
    occurrences in [window_start, window_end]."""
    stats = HorizonStats()

    slots = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(window_start, window_end),
        )
    )).scalars().all()
    slot_ids = [s.id for s in slots]

    booked_by_slot: dict[uuid.UUID, int] = {}
    campaign_by_slot: dict[uuid.UUID, RecruitmentCampaign] = {}
    if slot_ids:
        booked_rows = (await db.execute(
            select(Booking.event_slot_id, func.count())
            .where(
                Booking.tenant_id == tenant.id,
                Booking.event_slot_id.in_(slot_ids),
                Booking.status != BookingStatus.CANCELLED,
            )
            .group_by(Booking.event_slot_id)
        )).all()
        booked_by_slot = {sid: int(n) for sid, n in booked_rows}

        camp_rows = (await db.execute(
            select(RecruitmentCampaign).where(
                RecruitmentCampaign.tenant_id == tenant.id,
                RecruitmentCampaign.event_slot_id.in_(slot_ids),
            )
        )).scalars().all()
        for c in camp_rows:
            campaign_by_slot.setdefault(c.event_slot_id, c)

    for slot in slots:
        capacity = 0
        min_required = 0
        for s in (slot.service_config or []):
            try:
                capacity += int(s.get("max_allowed", 0) or 0)
                min_required += int(s.get("min_required", 0) or 0)
            except (TypeError, ValueError):
                continue
        if capacity == 0:
            continue
        booked = booked_by_slot.get(slot.id, 0)
        stats.events_count += 1
        stats.specific_count += 1
        stats.total_required += min_required
        stats.open_min += max(0, min_required - booked)
        if booked < min_required:
            stats.at_risk += 1
        camp = campaign_by_slot.get(slot.id)
        if camp is not None and camp.status not in _TERMINAL_CAMPAIGN_STATUSES:
            stats.campaigns_running += 1

    # Recurring occurrences — skip dates already materialized to the same rule.
    rules = (await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.is_active.is_(True),
        )
    )).scalars().all()
    materialized_rule_dates: set[tuple[uuid.UUID, date]] = {
        (s.availability_rule_id, s.date)
        for s in slots
        if s.availability_rule_id is not None
    }

    rec_bookings_by_day_type: dict[tuple[date, uuid.UUID], int] = {}
    if rules:
        day_start_utc = datetime.combine(window_start, time.min, tzinfo=timezone.utc)
        day_end_utc = datetime.combine(window_end, time.max, tzinfo=timezone.utc)
        rec_rows = (await db.execute(
            select(Booking.scheduled_at, Booking.appointment_type_id)
            .where(
                Booking.tenant_id == tenant.id,
                Booking.event_slot_id.is_(None),
                Booking.scheduled_at.between(day_start_utc, day_end_utc),
                Booking.status != BookingStatus.CANCELLED,
            )
        )).all()
        for sched_at, type_id in rec_rows:
            if type_id is None:
                continue
            key = (sched_at.date(), type_id)
            rec_bookings_by_day_type[key] = rec_bookings_by_day_type.get(key, 0) + 1

    one_day = timedelta(days=1)
    cur = window_start
    while cur <= window_end:
        dow = cur.weekday()
        for rule in rules:
            if rule.day_of_week != dow:
                continue
            if (rule.id, cur) in materialized_rule_dates:
                continue
            capacity = 0
            min_required = 0
            booked = 0
            for svc in (rule.service_config or []):
                try:
                    capacity += int(svc.get("max_allowed", 0) or 0)
                    min_required += int(svc.get("min_required", 0) or 0)
                    tid_raw = svc.get("appointment_type_id")
                    if tid_raw:
                        tid = (
                            tid_raw
                            if isinstance(tid_raw, uuid.UUID)
                            else uuid.UUID(str(tid_raw))
                        )
                        booked += rec_bookings_by_day_type.get((cur, tid), 0)
                except (TypeError, ValueError):
                    continue
            if capacity == 0:
                continue
            stats.events_count += 1
            stats.recurring_count += 1
            stats.total_required += min_required
            stats.open_min += max(0, min_required - booked)
            if booked < min_required:
                stats.at_risk += 1
            # Recurring has no campaign until materialized; campaigns_running unchanged.
        cur += one_day

    return stats


async def compute_kpi_summary(
    db: AsyncSession,
    tenant: Tenant,
) -> KpiSummary:
    """Build the two-horizon snapshot for a tenant."""
    today = date.today()
    summary = KpiSummary(
        tenant_name=tenant.name or tenant.slug or "",
        as_of=datetime.now(timezone.utc),
    )
    summary.immediate = await _aggregate_horizon(
        db, tenant, today, today + timedelta(days=14)
    )
    summary.planning = await _aggregate_horizon(
        db, tenant, today + timedelta(days=15), today + timedelta(days=60)
    )
    return summary


def format_kpi_summary_sms(summary: KpiSummary) -> str:
    """SMS-friendly text. Two short blocks, one per horizon, with
    enough numbers for an admin to know whether anything needs a
    decision without opening the dashboard.

    Stays under ~480 chars so a Twilio segment count is predictable."""
    def block(label: str, h: HorizonStats) -> str:
        if h.events_count == 0:
            return f"{label}: no events"
        return (
            f"{label}: {h.events_count} events "
            f"({h.recurring_count} rec / {h.specific_count} one-time)\n"
            f"  Open slots: {h.open_min}/{h.total_required}\n"
            f"  At-risk: {h.at_risk}  |  "
            f"Campaigns: {h.campaigns_running}/{h.events_count}"
        )

    return (
        f"{summary.tenant_name} — daily status\n\n"
        f"{block('Next 2 weeks', summary.immediate)}\n\n"
        f"{block('Weeks 3-8', summary.planning)}"
    )
