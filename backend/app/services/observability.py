"""Observability metrics service (decision #33).

One function per metric. Each takes (tenant_id, window_start, window_end)
and returns a typed result. Same service powers both the tenant-scoped
view (OWNER/MANAGER) and the SUPER_ADMIN per-tenant drill-down.

Phase 1 metrics:
  - check_in_completion_rate
  - late_check_in_rate
  - auto_close_rate
  - admin_vs_volunteer_checkin_split
  - re_entry_rate
  - walkup_candidate_volume
  - candidate_promote_dismiss_split
  - candidate_auto_prune_volume

Later phases bolt on more metrics here as features ship.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser
from app.models.booking import Booking, BookingStatus
from app.models.agent_call_log import AgentCallLog
from app.models.booking_review import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_NO_SHOW,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_SKIPPED,
    BookingReview,
)
from app.models.booking_service_log import (
    BSL_STATUS_APPROVED,
    BSL_STATUS_PENDING,
    BSL_STATUS_REJECTED,
    BSL_STATUS_SUPERSEDED,
    BookingServiceLog,
)
from app.models.award_definition import AwardDefinition
from app.models.contact import Contact
from app.models.roster_status_ping_log import RosterStatusPingLog
from app.models.volunteer_candidate import VolunteerCandidate
from app.models.volunteer_recognition import VolunteerRecognition


@dataclass
class MetricResult:
    """Generic metric result container."""
    label: str
    value: float
    numerator: int
    denominator: int
    extra: dict | None = None


async def check_in_completion_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """% of bookings (in window) with a checked_in_at timestamp."""
    base = select(func.count()).where(
        Booking.tenant_id == tenant_id,
        Booking.created_at.between(window_start, window_end),
        Booking.status != BookingStatus.CANCELLED,
    )
    total = (await db.execute(base)).scalar_one()
    checked_in_q = base.where(Booking.checked_in_at.is_not(None))
    checked_in = (await db.execute(checked_in_q)).scalar_one()
    rate = (checked_in / total) if total else 0.0
    return MetricResult(
        label="check_in_completion_rate",
        value=round(rate, 4),
        numerator=int(checked_in),
        denominator=int(total),
    )


async def admin_vs_volunteer_checkin_split(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of check-ins initiated by admin override vs volunteer SMS."""
    result = await db.execute(
        select(Booking.checked_in_source, func.count()).where(
            Booking.tenant_id == tenant_id,
            Booking.checked_in_at.between(window_start, window_end),
            Booking.checked_in_source.is_not(None),
        ).group_by(Booking.checked_in_source)
    )
    counts: dict[str, int] = {row[0]: int(row[1]) for row in result.all()}
    total = sum(counts.values())
    admin_count = (
        counts.get("admin_override", 0)
        + counts.get("admin_initial", 0)
    )
    return MetricResult(
        label="admin_vs_volunteer_checkin_split",
        value=round(admin_count / total, 4) if total else 0.0,
        numerator=admin_count,
        denominator=total,
        extra={"per_source": counts},
    )


async def auto_close_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """% of check-outs that were auto-closed by the T+end+1h job."""
    base = select(func.count()).where(
        Booking.tenant_id == tenant_id,
        Booking.checked_out_at.between(window_start, window_end),
    )
    total = (await db.execute(base)).scalar_one()
    auto_q = base.where(Booking.checked_out_source == "auto_close")
    auto_count = (await db.execute(auto_q)).scalar_one()
    return MetricResult(
        label="auto_close_rate",
        value=round(auto_count / total, 4) if total else 0.0,
        numerator=int(auto_count),
        denominator=int(total),
    )


async def walkup_candidate_volume(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Count of new VolunteerCandidate rows created in the window."""
    base = select(func.count()).where(
        VolunteerCandidate.tenant_id == tenant_id,
        VolunteerCandidate.first_seen_at.between(window_start, window_end),
    )
    count = (await db.execute(base)).scalar_one()
    return MetricResult(
        label="walkup_candidate_volume",
        value=float(count),
        numerator=int(count),
        denominator=int(count),
    )


async def candidate_promote_dismiss_split(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """For candidates that left 'new' status in the window, what fraction
    were invited vs dismissed?"""
    result = await db.execute(
        select(VolunteerCandidate.status, func.count()).where(
            VolunteerCandidate.tenant_id == tenant_id,
            (
                (VolunteerCandidate.invited_at.between(window_start, window_end))
                | (VolunteerCandidate.dismissed_at.between(window_start, window_end))
            ),
            VolunteerCandidate.status != "new",
        ).group_by(VolunteerCandidate.status)
    )
    counts: dict[str, int] = {row[0]: int(row[1]) for row in result.all()}
    invited = counts.get("invited", 0)
    dismissed = counts.get("dismissed", 0)
    total = invited + dismissed
    return MetricResult(
        label="candidate_promote_dismiss_split",
        value=round(invited / total, 4) if total else 0.0,
        numerator=invited,
        denominator=total,
        extra={"invited": invited, "dismissed": dismissed},
    )


# ── Phase 2 metrics — Roster status auto-pings ─────────────────────


async def pings_sent_volume(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Total ping rows (across all channels + statuses) in the window.

    Useful as the denominator for opt-out / suppression rates.
    """
    base = select(func.count()).where(
        RosterStatusPingLog.tenant_id == tenant_id,
        RosterStatusPingLog.scheduled_for.between(window_start, window_end),
    )
    total = (await db.execute(base)).scalar_one()
    return MetricResult(
        label="pings_sent_volume",
        value=float(total),
        numerator=int(total),
        denominator=int(total),
    )


async def stop_status_optout_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of (admin, slot) ping schedules that were silenced by
    STOP STATUS / STOP STATUS ALL (skipped_reason='admin_silenced').
    """
    base = select(func.count()).where(
        RosterStatusPingLog.tenant_id == tenant_id,
        RosterStatusPingLog.scheduled_for.between(window_start, window_end),
    )
    total = (await db.execute(base)).scalar_one()
    silenced = (await db.execute(
        base.where(RosterStatusPingLog.skipped_reason == "admin_silenced")
    )).scalar_one()
    return MetricResult(
        label="stop_status_optout_rate",
        value=round(silenced / total, 4) if total else 0.0,
        numerator=int(silenced),
        denominator=int(total),
    )


async def all_checked_in_suppression_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of scheduled pings suppressed because everyone was
    already checked in (skipped_reason='event_full_checked_in').
    """
    base = select(func.count()).where(
        RosterStatusPingLog.tenant_id == tenant_id,
        RosterStatusPingLog.scheduled_for.between(window_start, window_end),
    )
    total = (await db.execute(base)).scalar_one()
    suppressed = (await db.execute(
        base.where(
            RosterStatusPingLog.skipped_reason == "event_full_checked_in"
        )
    )).scalar_one()
    return MetricResult(
        label="all_checked_in_suppression_rate",
        value=round(suppressed / total, 4) if total else 0.0,
        numerator=int(suppressed),
        denominator=int(total),
    )


async def dispatch_failed_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of attempted dispatches that failed (Twilio errors)."""
    base = select(func.count()).where(
        RosterStatusPingLog.tenant_id == tenant_id,
        RosterStatusPingLog.scheduled_for.between(window_start, window_end),
    )
    # Rows that were attempted (i.e. not silenced/suppressed up front).
    attempted = (await db.execute(
        base.where(
            (RosterStatusPingLog.skipped_reason.is_(None))
            | (RosterStatusPingLog.skipped_reason == "dispatch_failed")
        )
    )).scalar_one()
    failed = (await db.execute(
        base.where(RosterStatusPingLog.skipped_reason == "dispatch_failed")
    )).scalar_one()
    return MetricResult(
        label="dispatch_failed_rate",
        value=round(failed / attempted, 4) if attempted else 0.0,
        numerator=int(failed),
        denominator=int(attempted),
    )


# ── Phase 3 metrics — Service log + mid-event switch ───────────────


async def switch_request_volume(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Total SWITCH/ALSO requests created in the window
    (booking_service_log rows with source='volunteer_sms')."""
    base = select(func.count()).where(
        BookingServiceLog.tenant_id == tenant_id,
        BookingServiceLog.created_at.between(window_start, window_end),
        BookingServiceLog.source == "volunteer_sms",
    )
    total = (await db.execute(base)).scalar_one()
    return MetricResult(
        label="switch_request_volume",
        value=float(total),
        numerator=int(total),
        denominator=int(total),
    )


async def approval_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of pending requests approved vs rejected (excluding
    still-pending and superseded). Denominator excludes superseded so
    the metric tracks admin decisions, not volunteer churn.
    """
    base = select(func.count()).where(
        BookingServiceLog.tenant_id == tenant_id,
        BookingServiceLog.created_at.between(window_start, window_end),
        BookingServiceLog.source == "volunteer_sms",
    )
    approved = (await db.execute(
        base.where(BookingServiceLog.status == BSL_STATUS_APPROVED)
    )).scalar_one()
    rejected = (await db.execute(
        base.where(BookingServiceLog.status == BSL_STATUS_REJECTED)
    )).scalar_one()
    decisioned = approved + rejected
    return MetricResult(
        label="approval_rate",
        value=round(approved / decisioned, 4) if decisioned else 0.0,
        numerator=int(approved),
        denominator=int(decisioned),
        extra={"approved": int(approved), "rejected": int(rejected)},
    )


async def supersede_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """% of created requests that ended up superseded by a later
    request from the same booking. High supersede rate = volunteer
    churn / picker UX problem.
    """
    base = select(func.count()).where(
        BookingServiceLog.tenant_id == tenant_id,
        BookingServiceLog.created_at.between(window_start, window_end),
        BookingServiceLog.source == "volunteer_sms",
    )
    total = (await db.execute(base)).scalar_one()
    superseded = (await db.execute(
        base.where(BookingServiceLog.status == BSL_STATUS_SUPERSEDED)
    )).scalar_one()
    return MetricResult(
        label="supersede_rate",
        value=round(superseded / total, 4) if total else 0.0,
        numerator=int(superseded),
        denominator=int(total),
    )


async def approval_latency_seconds(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Approval latency stats — p50 / p95 / max in seconds. Reported as
    a single MetricResult whose `value` is p50 and `extra` holds p95
    and max for the distribution.
    """
    rows_q = await db.execute(
        select(
            func.extract(
                "epoch",
                BookingServiceLog.approved_at - BookingServiceLog.created_at,
            ).label("latency_s")
        ).where(
            BookingServiceLog.tenant_id == tenant_id,
            BookingServiceLog.created_at.between(window_start, window_end),
            BookingServiceLog.source == "volunteer_sms",
            BookingServiceLog.approved_at.is_not(None),
            BookingServiceLog.status.in_([BSL_STATUS_APPROVED, BSL_STATUS_REJECTED]),
        )
    )
    latencies = sorted(float(r[0]) for r in rows_q.all() if r[0] is not None)
    n = len(latencies)
    if n == 0:
        return MetricResult(
            label="approval_latency_seconds",
            value=0.0,
            numerator=0,
            denominator=0,
            extra={"p50": 0, "p95": 0, "max": 0, "n": 0},
        )

    def _percentile(p: float) -> float:
        idx = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return latencies[idx]

    p50 = _percentile(50)
    p95 = _percentile(95)
    mx = latencies[-1]
    return MetricResult(
        label="approval_latency_seconds",
        value=round(p50, 1),
        numerator=int(p50),
        denominator=n,
        extra={
            "p50": round(p50, 1),
            "p95": round(p95, 1),
            "max": round(mx, 1),
            "n": n,
        },
    )


# ── Phase 4 metrics — Post-event review + grading ──────────────────


async def review_approval_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Fraction of reviews in the window that are in a terminal-approved
    or terminal-skipped state vs. still pending. Excludes no_show
    (auto-created and meaningful as-is)."""
    base = select(func.count()).where(
        BookingReview.tenant_id == tenant_id,
        BookingReview.created_at.between(window_start, window_end),
        BookingReview.status != REVIEW_STATUS_NO_SHOW,
    )
    total = (await db.execute(base)).scalar_one()
    approved = (await db.execute(
        base.where(BookingReview.status == REVIEW_STATUS_APPROVED)
    )).scalar_one()
    return MetricResult(
        label="review_approval_rate",
        value=round(approved / total, 4) if total else 0.0,
        numerator=int(approved),
        denominator=int(total),
    )


async def time_to_review_seconds(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """p50 / p95 / max time-to-review in seconds: created_at → reviewed_at
    for the approved set."""
    rows_q = await db.execute(
        select(
            func.extract(
                "epoch",
                BookingReview.reviewed_at - BookingReview.created_at,
            ).label("latency_s")
        ).where(
            BookingReview.tenant_id == tenant_id,
            BookingReview.created_at.between(window_start, window_end),
            BookingReview.status == REVIEW_STATUS_APPROVED,
            BookingReview.reviewed_at.is_not(None),
        )
    )
    latencies = sorted(float(r[0]) for r in rows_q.all() if r[0] is not None)
    n = len(latencies)
    if n == 0:
        return MetricResult(
            label="time_to_review_seconds",
            value=0.0,
            numerator=0,
            denominator=0,
            extra={"p50": 0, "p95": 0, "max": 0, "n": 0},
        )

    def _percentile(p: float) -> float:
        idx = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return latencies[idx]

    p50 = _percentile(50)
    p95 = _percentile(95)
    mx = latencies[-1]
    return MetricResult(
        label="time_to_review_seconds",
        value=round(p50, 1),
        numerator=int(p50),
        denominator=n,
        extra={
            "p50": round(p50, 1),
            "p95": round(p95, 1),
            "max": round(mx, 1),
            "n": n,
        },
    )


async def grade_distribution(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Histogram of approved grades in the window. Returns the average
    grade as `value` and the per-grade counts in `extra`."""
    rows = await db.execute(
        select(BookingReview.grade, func.count()).where(
            BookingReview.tenant_id == tenant_id,
            BookingReview.created_at.between(window_start, window_end),
            BookingReview.status == REVIEW_STATUS_APPROVED,
            BookingReview.grade.is_not(None),
        ).group_by(BookingReview.grade)
    )
    counts: dict[int, int] = {int(g): int(c) for g, c in rows.all()}
    total = sum(counts.values())
    if total == 0:
        avg = 0.0
    else:
        avg = sum(g * c for g, c in counts.items()) / total
    return MetricResult(
        label="grade_distribution",
        value=round(avg, 2),
        numerator=total,
        denominator=total,
        extra={
            "grade_1": counts.get(1, 0),
            "grade_2": counts.get(2, 0),
            "grade_3": counts.get(3, 0),
            "grade_4": counts.get(4, 0),
            "grade_5": counts.get(5, 0),
            "avg": round(avg, 2),
        },
    )


async def consider_striking_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """% of approved reviews where the admin assigned grade=1 (the
    'Consider striking?' flag). Decision #15 — never auto-strike; this
    is a surfaced UI nudge only."""
    base = select(func.count()).where(
        BookingReview.tenant_id == tenant_id,
        BookingReview.created_at.between(window_start, window_end),
        BookingReview.status == REVIEW_STATUS_APPROVED,
        BookingReview.grade.is_not(None),
    )
    total = (await db.execute(base)).scalar_one()
    grade_one = (await db.execute(
        base.where(BookingReview.grade == 1)
    )).scalar_one()
    return MetricResult(
        label="consider_striking_rate",
        value=round(grade_one / total, 4) if total else 0.0,
        numerator=int(grade_one),
        denominator=int(total),
    )


async def owner_unlock_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Count of review_unlocked audit entries in the window with
    admin_role == 'owner' (OWNER 24h grace unlocks per decision #16)."""
    rows = await db.execute(
        select(AgentCallLog.payload).where(
            AgentCallLog.tenant_id == tenant_id,
            AgentCallLog.event_type == "review_unlocked",
            AgentCallLog.created_at.between(window_start, window_end),
        )
    )
    payloads = [p[0] for p in rows.all() if p[0] is not None]
    owner_count = sum(
        1 for p in payloads if (p or {}).get("admin_role") == "owner"
    )
    total = len(payloads)
    return MetricResult(
        label="owner_unlock_rate",
        value=round(owner_count / total, 4) if total else 0.0,
        numerator=owner_count,
        denominator=total,
    )


async def super_admin_unlock_rate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Sibling of owner_unlock_rate — surface SUPER_ADMIN unlocks
    separately so a spike (e.g. cleaning up contested reviews) is visible.
    """
    rows = await db.execute(
        select(AgentCallLog.payload).where(
            AgentCallLog.tenant_id == tenant_id,
            AgentCallLog.event_type == "review_unlocked",
            AgentCallLog.created_at.between(window_start, window_end),
        )
    )
    payloads = [p[0] for p in rows.all() if p[0] is not None]
    super_count = sum(
        1 for p in payloads if (p or {}).get("admin_role") == "super_admin"
    )
    total = len(payloads)
    return MetricResult(
        label="super_admin_unlock_rate",
        value=round(super_count / total, 4) if total else 0.0,
        numerator=super_count,
        denominator=total,
    )


# ── Phase 5 metrics — Recognition (milestones / badges / awards) ───


async def recognitions_earned_per_kind(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Count of recognitions earned in the window, broken down by kind
    (milestone / badge / award). Total is `value`; per-kind counts in extras."""
    rows = await db.execute(
        select(AwardDefinition.kind, func.count(VolunteerRecognition.id))
        .join(
            VolunteerRecognition,
            VolunteerRecognition.definition_id == AwardDefinition.id,
        )
        .where(
            VolunteerRecognition.tenant_id == tenant_id,
            VolunteerRecognition.earned_at.between(window_start, window_end),
        )
        .group_by(AwardDefinition.kind)
    )
    counts: dict[str, int] = {kind: int(c) for kind, c in rows.all()}
    total = sum(counts.values())
    return MetricResult(
        label="recognitions_earned_per_kind",
        value=float(total),
        numerator=total,
        denominator=total,
        extra={
            "milestone": counts.get("milestone", 0),
            "badge": counts.get("badge", 0),
            "award": counts.get("award", 0),
        },
    )


async def congrats_sms_dispatch_volume(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Approximate proxy: count of recognitions earned in the window. The
    congratulatory SMS fires synchronously inside the engine (best-effort);
    actual dispatch success depends on tenant opt-in + per-contact phone.

    Phase 5 keeps this as the headline number since wiring up the actual
    Twilio delivery log per-tenant is out of scope.
    """
    base = select(func.count()).where(
        VolunteerRecognition.tenant_id == tenant_id,
        VolunteerRecognition.earned_at.between(window_start, window_end),
    )
    total = (await db.execute(base)).scalar_one()
    return MetricResult(
        label="congrats_sms_dispatch_volume",
        value=float(total),
        numerator=int(total),
        denominator=int(total),
    )


async def quality_score_distribution(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Per-tenant histogram of contacts.historical_quality_score, bucketed
    into the recruiter targeting bands (cold-start, low, neutral, high).

    Window is informational only — the score is point-in-time; we just
    pull whoever currently has a score (regardless of when last updated)
    and bucket them. `value` is the mean across all scored contacts.
    """
    rows = await db.execute(
        select(Contact.historical_quality_score).where(
            Contact.tenant_id == tenant_id,
            Contact.historical_quality_score.is_not(None),
        )
    )
    scores = [float(r[0]) for r in rows.all() if r[0] is not None]
    if not scores:
        return MetricResult(
            label="quality_score_distribution",
            value=0.0,
            numerator=0,
            denominator=0,
            extra={"cold_start": 0, "low": 0, "neutral": 0, "high": 0, "mean": 0.0},
        )

    high = sum(1 for s in scores if s >= 4.0)
    low = sum(1 for s in scores if s < 2.5)
    neutral = len(scores) - high - low

    # cold_start = contacts with no score at all (separate query for clarity)
    cold_q = await db.execute(
        select(func.count()).where(
            Contact.tenant_id == tenant_id,
            Contact.historical_quality_score.is_(None),
        )
    )
    cold = int(cold_q.scalar() or 0)

    mean = sum(scores) / len(scores)
    return MetricResult(
        label="quality_score_distribution",
        value=round(mean, 2),
        numerator=len(scores),
        denominator=len(scores) + cold,
        extra={
            "cold_start": cold,
            "low": low,
            "neutral": neutral,
            "high": high,
            "mean": round(mean, 2),
        },
    )


async def candidate_auto_prune_volume(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> MetricResult:
    """Approximate proxy: count of candidates currently in 'dismissed' or
    'invited' terminal states (the auto-prune job's targets). Real
    deletions aren't logged anywhere by design (the row's gone).

    For a tighter version, the prune job could log to agent_call_log;
    Phase 5 keeps it as terminal-state count as a directional metric.
    """
    base = select(func.count()).where(
        VolunteerCandidate.tenant_id == tenant_id,
    )
    invited = (await db.execute(
        base.where(VolunteerCandidate.status == "invited")
    )).scalar_one()
    dismissed = (await db.execute(
        base.where(VolunteerCandidate.status == "dismissed")
    )).scalar_one()
    total = invited + dismissed
    return MetricResult(
        label="candidate_terminal_pool",
        value=float(total),
        numerator=int(total),
        denominator=int(total),
        extra={"invited": int(invited), "dismissed": int(dismissed)},
    )
