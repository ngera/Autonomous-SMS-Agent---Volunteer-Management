"""Pure recipient-selection layer for the Volunteer Recruitment Agent.

This module is the *only* place that decides who to message for a campaign
wave. All hard filters (consent, active, suspension, eligibility, cooldowns,
quiet hours, already-booked) are applied here and cannot be overridden by
policy. Final ranking uses a deterministic experience score.

Each service has a ``min_required`` floor and an optional ``max_allowed``
ceiling. Recruitment runs in two phases:
- ``min`` phase: fill toward ``min_required`` (must-have).
- ``max`` phase: once min is satisfied (across all competing campaigns for
  the same service), fill toward ``max_allowed`` (nice-to-have).

Scoring (per locked decision #3):
    +10 * count(bookings for THIS service in lookback,
                status in {SCHEDULED, RESCHEDULED, COMPLETED})
    + 2 * count(bookings for SAME-CATEGORY services in lookback, same statuses)
    - 5 * count(NO_SHOW bookings in lookback)
Tie-break: most recent qualifying booking first, then alphabetical by name.

The function is async because it touches the DB, but it has no side effects.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Sequence


Phase = Literal["min", "max"]

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.contact_preferred_type import ContactPreferredType
from app.models.recruitment_campaign import (
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)
from app.models.suspension import ContactSuspension, ReviewDecision


# Hard-filter defaults (overridable via campaign.policy)
DEFAULT_COOLDOWN_HOURS_WITHIN_CAMPAIGN = 48
DEFAULT_GLOBAL_PER_CONTACT_HOURS = 24
DEFAULT_EXPERIENCE_LOOKBACK_DAYS = 180
DEFAULT_OVERSHOOT_FACTOR = 1.5

POSITIVE_BOOKING_STATUSES = (
    BookingStatus.SCHEDULED,
    BookingStatus.RESCHEDULED,
    BookingStatus.COMPLETED,
)


@dataclass(frozen=True)
class ScoredContact:
    contact_id: uuid.UUID
    name: str | None
    phone: str
    score: float
    this_service_count: int
    same_category_count: int
    no_show_count: int
    most_recent_qualifying_at: datetime | None


@dataclass(frozen=True)
class TargetingResult:
    contacts: list[ScoredContact]
    eligible_pool_size: int   # before ranking + cap
    selection_reason: str


def _policy(campaign: RecruitmentCampaign) -> dict:
    return campaign.policy or {}


def _cooldown_hours(campaign: RecruitmentCampaign) -> int:
    return int(
        _policy(campaign).get(
            "cooldown_hours_within_campaign",
            DEFAULT_COOLDOWN_HOURS_WITHIN_CAMPAIGN,
        )
    )


def _global_cooldown_hours(campaign: RecruitmentCampaign) -> int:
    return int(
        _policy(campaign).get(
            "global_per_contact_hours",
            DEFAULT_GLOBAL_PER_CONTACT_HOURS,
        )
    )


def _lookback_days(campaign: RecruitmentCampaign) -> int:
    return int(
        _policy(campaign).get(
            "experience_lookback_days",
            DEFAULT_EXPERIENCE_LOOKBACK_DAYS,
        )
    )


def _overshoot_factor(campaign: RecruitmentCampaign) -> float:
    return float(_policy(campaign).get("overshoot_factor", DEFAULT_OVERSHOOT_FACTOR))


def _absolute_cap(campaign: RecruitmentCampaign) -> int | None:
    val = _policy(campaign).get("per_wave_absolute_cap")
    return int(val) if val is not None else None


def _goal_for(
    campaign: RecruitmentCampaign, service_id: uuid.UUID
) -> dict | None:
    for goal in campaign.goals or []:
        if str(goal.get("appointment_type_id")) == str(service_id):
            return goal
    return None


def _service_min(campaign: RecruitmentCampaign, service_id: uuid.UUID) -> int:
    """Per-service floor (must-have)."""
    g = _goal_for(campaign, service_id)
    if not g:
        return 0
    # Accept new (min_required) and legacy (target / min_acceptable) keys.
    val = g.get("min_required")
    if val is None:
        val = g.get("min_acceptable")
    if val is None:
        val = g.get("target", 0)
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _service_max(
    campaign: RecruitmentCampaign, service_id: uuid.UUID
) -> int | None:
    """Per-service ceiling (nice-to-have). None means no upper bound beyond min."""
    g = _goal_for(campaign, service_id)
    if not g:
        return None
    val = g.get("max_allowed")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _service_target(
    campaign: RecruitmentCampaign,
    service_id: uuid.UUID,
    phase: Phase = "min",
) -> int:
    """Return the fill target for the given phase.

    - ``min`` phase: ``min_required``.
    - ``max`` phase: ``max_allowed`` if set, otherwise ``min_required``.
    """
    if phase == "max":
        m = _service_max(campaign, service_id)
        if m is not None:
            return m
    return _service_min(campaign, service_id)


async def _current_signups_for_service(
    db: AsyncSession,
    event_slot: SpecificDateSlot,
    service_id: uuid.UUID,
) -> int:
    """Count bookings already filling this service slot for the event date."""
    result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.tenant_id == event_slot.tenant_id,
            Booking.appointment_type_id == service_id,
            func.date(Booking.scheduled_at) == event_slot.date,
            Booking.status.in_(
                [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
            ),
        )
    )
    return int(result.scalar() or 0)


async def _already_booked_in_event(
    db: AsyncSession,
    event_slot: SpecificDateSlot,
) -> set[uuid.UUID]:
    """Contacts with any non-cancelled booking on the event date — excluded
    from this event's recruitment regardless of which service they hold."""
    result = await db.execute(
        select(Booking.contact_id).where(
            Booking.tenant_id == event_slot.tenant_id,
            func.date(Booking.scheduled_at) == event_slot.date,
            Booking.status.in_(
                [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
            ),
        )
    )
    return set(result.scalars().all())


async def _within_campaign_cooldown(
    db: AsyncSession,
    campaign: RecruitmentCampaign,
    cooldown_hours: int,
) -> set[uuid.UUID]:
    """Contacts who received a wave in THIS campaign recently."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    waves = await db.execute(
        select(RecruitmentWave.targeted_contact_ids).where(
            RecruitmentWave.tenant_id == campaign.tenant_id,
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= cutoff,
        )
    )
    blocked: set[uuid.UUID] = set()
    for row in waves.scalars().all():
        for cid in row or []:
            try:
                blocked.add(uuid.UUID(str(cid)))
            except (ValueError, TypeError):
                continue
    return blocked


async def _within_global_cooldown(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    global_hours: int,
) -> set[uuid.UUID]:
    """Contacts who received ANY recruitment wave in the tenant recently.

    Prevents bombarding multi-skill volunteers when several events run in
    parallel. Looks across all campaigns in the tenant.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=global_hours)
    waves = await db.execute(
        select(RecruitmentWave.targeted_contact_ids).where(
            RecruitmentWave.tenant_id == tenant_id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= cutoff,
        )
    )
    blocked: set[uuid.UUID] = set()
    for row in waves.scalars().all():
        for cid in row or []:
            try:
                blocked.add(uuid.UUID(str(cid)))
            except (ValueError, TypeError):
                continue
    return blocked


async def _eligible_for_service(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    service_id: uuid.UUID,
) -> set[uuid.UUID]:
    all_enabled = await db.execute(
        select(Contact.id).where(
            Contact.tenant_id == tenant_id,
            Contact.all_services_enabled.is_(True),
        )
    )
    preferred = await db.execute(
        select(ContactPreferredType.contact_id).where(
            ContactPreferredType.tenant_id == tenant_id,
            ContactPreferredType.appointment_type_id == service_id,
        )
    )
    return set(all_enabled.scalars().all()) | set(preferred.scalars().all())


async def _opted_in_active_contacts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    candidate_ids: Sequence[uuid.UUID],
) -> list[Contact]:
    """Fetch Contact rows that pass consent + active + non-archived gates.

    Suspension is checked separately because it lives in its own table and
    can exist independently of ``Contact.status``.
    """
    if not candidate_ids:
        return []
    result = await db.execute(
        select(Contact)
        .join(ContactConsent, ContactConsent.contact_id == Contact.id)
        .where(
            Contact.tenant_id == tenant_id,
            Contact.id.in_(candidate_ids),
            Contact.status == ContactStatus.ACTIVE,
            Contact.is_archived.is_(False),
            # Decision #30 — admin-linked Contacts (and anyone who's
            # opted out via the toggle) get filtered out of wave
            # targeting. Strikes still own hard exclusion separately.
            Contact.exclude_from_recruiting.is_(False),
            ContactConsent.status == ConsentStatus.OPTED_IN,
        )
    )
    return list(result.scalars().all())


async def _active_suspensions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_ids: Sequence[uuid.UUID],
) -> set[uuid.UUID]:
    if not contact_ids:
        return set()
    result = await db.execute(
        select(ContactSuspension.contact_id).where(
            ContactSuspension.tenant_id == tenant_id,
            ContactSuspension.contact_id.in_(contact_ids),
            ContactSuspension.lifted_at.is_(None),
            or_(
                ContactSuspension.review_decision.is_(None),
                ContactSuspension.review_decision != ReviewDecision.LIFTED,
            ),
        )
    )
    return set(result.scalars().all())


async def _category_for_service(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    service_id: uuid.UUID,
) -> str | None:
    result = await db.execute(
        select(AppointmentType.category).where(
            AppointmentType.tenant_id == tenant_id,
            AppointmentType.id == service_id,
        )
    )
    return result.scalar_one_or_none()


async def _score_candidates(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    service_id: uuid.UUID,
    contacts: list[Contact],
    lookback_days: int,
) -> list[ScoredContact]:
    """Compute experience scores for each contact.

    Three SQL queries (one per signal) keyed by contact_id, then assembled
    in Python.
    """
    if not contacts:
        return []

    contact_ids = [c.id for c in contacts]
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    category = await _category_for_service(db, tenant_id, service_id)

    # +10: this-service positive bookings
    this_q = await db.execute(
        select(
            Booking.contact_id,
            func.count(Booking.id),
            func.max(Booking.scheduled_at),
        )
        .where(
            Booking.tenant_id == tenant_id,
            Booking.contact_id.in_(contact_ids),
            Booking.appointment_type_id == service_id,
            Booking.status.in_(POSITIVE_BOOKING_STATUSES),
            Booking.scheduled_at >= cutoff,
        )
        .group_by(Booking.contact_id)
    )
    this_map: dict[uuid.UUID, tuple[int, datetime]] = {
        row[0]: (int(row[1]), row[2]) for row in this_q.all()
    }

    # +2: same-category positive bookings (any service in this category)
    same_cat_map: dict[uuid.UUID, int] = {}
    if category:
        cat_q = await db.execute(
            select(Booking.contact_id, func.count(Booking.id))
            .join(
                AppointmentType,
                AppointmentType.id == Booking.appointment_type_id,
            )
            .where(
                Booking.tenant_id == tenant_id,
                Booking.contact_id.in_(contact_ids),
                AppointmentType.category == category,
                # Exclude THIS service so we don't double-count it
                Booking.appointment_type_id != service_id,
                Booking.status.in_(POSITIVE_BOOKING_STATUSES),
                Booking.scheduled_at >= cutoff,
            )
            .group_by(Booking.contact_id)
        )
        same_cat_map = {row[0]: int(row[1]) for row in cat_q.all()}

    # -5: no-show penalty (any service)
    ns_q = await db.execute(
        select(Booking.contact_id, func.count(Booking.id))
        .where(
            Booking.tenant_id == tenant_id,
            Booking.contact_id.in_(contact_ids),
            Booking.status == BookingStatus.NO_SHOW,
            Booking.scheduled_at >= cutoff,
        )
        .group_by(Booking.contact_id)
    )
    ns_map: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in ns_q.all()}

    # Phase 4 — pre-fetch per-tenant quality-weight SystemSettings (decision #24).
    # Read once per scoring call (rare) so per-contact lookups stay O(1).
    weights = await _resolve_quality_weights(db, tenant_id)

    scored: list[ScoredContact] = []
    for c in contacts:
        this_count, recent_ts = this_map.get(c.id, (0, None))
        cat_count = same_cat_map.get(c.id, 0)
        ns_count = ns_map.get(c.id, 0)
        raw_score = (10.0 * this_count) + (2.0 * cat_count) - (5.0 * ns_count)
        # Apply quality multiplier (decision #24). Cold-start contacts
        # (None score or 0 approved reviews) get the neutral weight.
        score = raw_score * _quality_weight(c, weights)
        scored.append(
            ScoredContact(
                contact_id=c.id,
                name=c.name,
                phone=c.phone,
                score=score,
                this_service_count=this_count,
                same_category_count=cat_count,
                no_show_count=ns_count,
                most_recent_qualifying_at=recent_ts,
            )
        )
    return scored


async def _resolve_quality_weights(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict:
    """Read tenant SystemSettings for the quality-weight multipliers
    (decision #24). Returns a dict with `high`, `neutral`, `low` keys."""
    from app.models.system_setting import SystemSetting

    keys = ("quality_weight_high", "quality_weight_neutral", "quality_weight_low")
    rows = (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key.in_(keys),
            )
        )
    ).scalars().all()
    by_key = {r.key: r.value for r in rows}

    def _as_float(key: str, default: float) -> float:
        try:
            return float(by_key.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "high": _as_float("quality_weight_high", 1.25),
        "neutral": _as_float("quality_weight_neutral", 1.0),
        "low": _as_float("quality_weight_low", 0.7),
    }


def _quality_weight(contact: Contact, weights: dict) -> float:
    """Map historical_quality_score to a soft ranking weight.

    Decision #24:
      Cold-start (None or 0 approved reviews) → neutral.
      Score >= 4 → high.
      Score 2.5–4 → neutral.
      Score < 2.5 → low (deprioritize, never exclude).

    `exclude_from_recruiting=True` contacts (admin-linked per decision #30)
    are filtered out upstream in the eligibility WHERE clause.
    """
    score = getattr(contact, "historical_quality_score", None)
    if score is None:
        return weights["neutral"]
    try:
        score_f = float(score)
    except (TypeError, ValueError):
        return weights["neutral"]
    if score_f >= 4.0:
        return weights["high"]
    if score_f < 2.5:
        return weights["low"]
    return weights["neutral"]


def _rank(scored: list[ScoredContact]) -> list[ScoredContact]:
    """Sort by score desc, then most-recent-qualifying-booking desc, then name asc."""
    def key(s: ScoredContact):
        # Sort tuples: higher score first → negate;
        # most recent timestamp first → negate via .timestamp() with fallback;
        # name ascending → use lowercased name with empty fallback.
        ts = s.most_recent_qualifying_at.timestamp() if s.most_recent_qualifying_at else 0.0
        name_key = (s.name or "").lower()
        return (-s.score, -ts, name_key)

    return sorted(scored, key=key)


def _wave_size(
    campaign: RecruitmentCampaign,
    service_id: uuid.UUID,
    current_signups: int,
    phase: Phase = "min",
) -> int:
    """How many contacts to message in this wave.

    ``ceil(gap * overshoot_factor)`` against the phase target, clamped by
    any policy absolute cap. Returns 0 when the gap is already satisfied.
    """
    target = _service_target(campaign, service_id, phase=phase)
    gap = max(0, target - current_signups)
    if gap == 0:
        return 0
    import math

    raw = math.ceil(gap * _overshoot_factor(campaign))
    cap = _absolute_cap(campaign)
    if cap is not None:
        raw = min(raw, cap)
    return max(1, raw)


async def select_recipients(
    db: AsyncSession,
    campaign: RecruitmentCampaign,
    event_slot: SpecificDateSlot,
    service_id: uuid.UUID,
    wave_number: int,
    phase: Phase = "min",
) -> TargetingResult:
    """Resolve the contact list to message for one wave.

    All hard filters are applied here. The returned ``contacts`` list is
    ranked by score and capped by wave size; the caller (``executor``) is
    responsible for rendering messages and creating the ``Announcement`` row.
    """
    tenant_id = campaign.tenant_id

    # Gate 1: service eligibility
    service_eligible = await _eligible_for_service(db, tenant_id, service_id)
    if not service_eligible:
        return TargetingResult(
            contacts=[],
            eligible_pool_size=0,
            selection_reason="No contacts configured for this service.",
        )

    # Gate 2: opted-in + active + not archived
    candidates = await _opted_in_active_contacts(
        db, tenant_id, list(service_eligible)
    )
    if not candidates:
        return TargetingResult(
            contacts=[],
            eligible_pool_size=0,
            selection_reason="No opted-in, active contacts eligible for this service.",
        )

    # Gate 3: not actively suspended
    suspended = await _active_suspensions(
        db, tenant_id, [c.id for c in candidates]
    )
    candidates = [c for c in candidates if c.id not in suspended]

    # Gate 4: not already booked on this event
    already_booked = await _already_booked_in_event(db, event_slot)
    candidates = [c for c in candidates if c.id not in already_booked]

    # Gate 5: cooldowns
    in_campaign_recent = await _within_campaign_cooldown(
        db, campaign, _cooldown_hours(campaign)
    )
    global_recent = await _within_global_cooldown(
        db, tenant_id, _global_cooldown_hours(campaign)
    )
    candidates = [
        c for c in candidates
        if c.id not in in_campaign_recent and c.id not in global_recent
    ]

    eligible_pool_size = len(candidates)
    if not candidates:
        return TargetingResult(
            contacts=[],
            eligible_pool_size=0,
            selection_reason=(
                "All otherwise-eligible contacts are within cooldown windows."
            ),
        )

    # Score + rank
    scored = await _score_candidates(
        db, tenant_id, service_id, candidates, _lookback_days(campaign)
    )
    ranked = _rank(scored)

    # Cap by wave size (driven by current signups vs phase target)
    current_signups = await _current_signups_for_service(
        db, event_slot, service_id
    )
    phase_target = _service_target(campaign, service_id, phase=phase)
    size = _wave_size(campaign, service_id, current_signups, phase=phase)
    if size == 0:
        return TargetingResult(
            contacts=[],
            eligible_pool_size=eligible_pool_size,
            selection_reason=(
                f"Service already at {phase} target "
                f"({current_signups}/{phase_target})."
            ),
        )

    selected = ranked[:size]
    reason = (
        f"Wave {wave_number} ({phase}-phase): top {len(selected)} of "
        f"{eligible_pool_size} eligible (target {phase_target}, current "
        f"{current_signups}, overshoot {_overshoot_factor(campaign):.2f})."
    )
    return TargetingResult(
        contacts=selected,
        eligible_pool_size=eligible_pool_size,
        selection_reason=reason,
    )
