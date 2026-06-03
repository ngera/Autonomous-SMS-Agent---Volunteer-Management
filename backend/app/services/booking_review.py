"""Phase 4 — post-event review service.

Owns the booking_review lifecycle:
  - reconstruct_segments_from_audit_log()  — multi-segment hours (decision #10)
  - create_pending_review_for_booking()    — used by T+end+grace scheduler
  - create_no_show_review_for_booking()    — used by T+start+30min scheduler
  - approve_review()                       — admin → 'approved', recompute quality
  - unlock_review() / can_unlock_review()  — OWNER 24h grace + SUPER_ADMIN
  - skip_review() / flip_no_show_to_pending()
  - recompute_quality_score_for_contact()  — soft-target weight input

Hours derivation (decision #10):
  - First segment's start_at clamped to slot.start_at - early_credit_minutes
  - Subsequent segments contribute their full duration (no early credit twice)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AGENT_ENGAGEMENT,
    EVENT_REVIEW_UNLOCKED,
)
from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
from app.models.agent_call_log import AgentCallLog
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.booking_review import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_NO_SHOW,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_SKIPPED,
    BookingReview,
)
from app.models.contact import Contact

logger = get_logger("booking_review")


# Default tenant SystemSetting values for Phase 4 (decisions #5, #10).
DEFAULT_REVIEW_GRACE_MINUTES = 120
DEFAULT_EARLY_CHECKIN_CREDIT_MINUTES = 30
DEFAULT_QUALITY_RECENT_N = 10  # decay-window for quality recompute


class ReviewImmutableError(Exception):
    """Raised when trying to mutate an approved/finalized review without
    going through unlock_review() first."""


# ── SystemSettings helpers ──────────────────────────────────────────


async def _get_setting_int(
    db: AsyncSession, tenant_id: uuid.UUID, key: str, default: int
) -> int:
    from app.models.system_setting import SystemSetting

    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return default
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return default


# ── Hours derivation (decision #10) ─────────────────────────────────


async def reconstruct_segments_from_audit_log(
    db: AsyncSession, *, booking: Booking
) -> list[dict]:
    """Build the segments JSONB array by pairing volunteer_check_in /
    volunteer_check_out events for this booking.

    The booking row itself holds the *current* segment (Phase 1 design).
    The audit log holds all historical (check_in, check_out) pairs from
    re-entry. We pair them in chronological order; trailing check_in
    without matching check_out is closed via the booking row's current
    state (or skipped if booking still open).
    """
    result = await db.execute(
        select(AgentCallLog).where(
            AgentCallLog.tenant_id == booking.tenant_id,
            AgentCallLog.event_type.in_(
                ["volunteer_check_in", "volunteer_check_out"]
            ),
        ).order_by(AgentCallLog.created_at)
    )
    rows = list(result.scalars().all())

    # Filter to events matching this booking_id (payload may or may not
    # contain it depending on emit-site; engagement intents always do).
    relevant = []
    for r in rows:
        payload = r.payload or {}
        if str(payload.get("booking_id")) == str(booking.id):
            relevant.append(r)

    segments: list[dict] = []
    current_in: AgentCallLog | None = None
    for ev in relevant:
        if ev.event_type == "volunteer_check_in":
            current_in = ev
        elif ev.event_type == "volunteer_check_out" and current_in is not None:
            segments.append(
                {
                    "in": _payload_iso(current_in.payload, "at")
                    or current_in.created_at.isoformat(),
                    "out": _payload_iso(ev.payload, "at")
                    or ev.created_at.isoformat(),
                    "source_in": (current_in.payload or {}).get("source"),
                    "source_out": (ev.payload or {}).get("source"),
                }
            )
            current_in = None

    # Trailing check-in without matching check-out: close via booking row.
    if current_in is not None and booking.checked_out_at is not None:
        segments.append(
            {
                "in": _payload_iso(current_in.payload, "at")
                or current_in.created_at.isoformat(),
                "out": booking.checked_out_at.isoformat(),
                "source_in": (current_in.payload or {}).get("source"),
                "source_out": booking.checked_out_source,
            }
        )

    # Empty audit log + booking has current state: fall back to a single
    # segment from booking columns.
    if not segments and booking.checked_in_at and booking.checked_out_at:
        segments.append(
            {
                "in": booking.checked_in_at.isoformat(),
                "out": booking.checked_out_at.isoformat(),
                "source_in": booking.checked_in_source,
                "source_out": booking.checked_out_source,
            }
        )
    return segments


def _payload_iso(payload: dict | None, key: str) -> str | None:
    if not payload:
        return None
    v = payload.get(key)
    return v if isinstance(v, str) else None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Accept both 'Z' suffix and offset-aware ISO strings.
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def compute_total_hours(
    segments: list[dict],
    slot_start_utc: datetime,
    early_credit_minutes: int,
) -> Decimal:
    """Decision #10 — multi-segment hours with early-credit floor on
    the first segment only. Result is rounded to 2 decimal places.
    """
    if not segments:
        return Decimal("0.00")
    floor = slot_start_utc - timedelta(minutes=early_credit_minutes)
    total_seconds = 0.0
    for i, seg in enumerate(segments):
        seg_in = _parse_iso(seg.get("in"))
        seg_out = _parse_iso(seg.get("out"))
        if seg_in is None or seg_out is None:
            continue
        # First segment: apply early-credit floor; subsequent segments
        # contribute their full duration.
        if i == 0:
            effective_in = max(seg_in, floor)
        else:
            effective_in = seg_in
        delta = (seg_out - effective_in).total_seconds()
        if delta > 0:
            total_seconds += delta
    return Decimal(total_seconds / 3600.0).quantize(Decimal("0.01"))


# ── Review creation ────────────────────────────────────────────────


async def _slot_start_utc(
    db: AsyncSession, slot: SpecificDateSlot, tenant_id: uuid.UUID
) -> datetime:
    """Translate slot.date+start_time to UTC using the tenant's timezone."""
    from app.models.tenant import Tenant
    import pytz

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    tz = pytz.timezone(tenant.business_timezone or "America/New_York")
    local_dt = tz.localize(datetime.combine(slot.date, slot.start_time))
    return local_dt.astimezone(timezone.utc)


async def create_pending_review_for_booking(
    db: AsyncSession, *, booking: Booking, slot: SpecificDateSlot
) -> BookingReview | None:
    """Idempotent — returns None if a review already exists for this
    booking. Otherwise inserts a 'pending' row, reconstructs segments
    + total_hours snapshot upfront so admin sees them on the form.
    """
    existing = await db.execute(
        select(BookingReview).where(BookingReview.booking_id == booking.id)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    segments = await reconstruct_segments_from_audit_log(db, booking=booking)
    slot_start = await _slot_start_utc(db, slot, booking.tenant_id)
    early_min = await _get_setting_int(
        db, booking.tenant_id, "early_checkin_credit_minutes",
        DEFAULT_EARLY_CHECKIN_CREDIT_MINUTES,
    )
    total_hours = compute_total_hours(segments, slot_start, early_min)

    first_in = _parse_iso(segments[0]["in"]) if segments else None
    last_out = _parse_iso(segments[-1]["out"]) if segments else None

    review = BookingReview(
        tenant_id=booking.tenant_id,
        booking_id=booking.id,
        status=REVIEW_STATUS_PENDING,
        segments=segments or None,
        total_hours=total_hours,
        final_check_in_at=first_in or booking.checked_in_at,
        final_check_out_at=last_out or booking.checked_out_at,
    )
    db.add(review)
    await db.flush()
    return review


async def create_no_show_review_for_booking(
    db: AsyncSession, *, booking: Booking
) -> BookingReview | None:
    """T+start+30min auto-creation (decision #14). Idempotent.

    Skips if a review already exists OR the booking has a check-in
    (admin marked them in retroactively before this tick fired).
    """
    existing = await db.execute(
        select(BookingReview).where(BookingReview.booking_id == booking.id)
    )
    if existing.scalar_one_or_none() is not None:
        return None
    if booking.checked_in_at is not None:
        return None

    review = BookingReview(
        tenant_id=booking.tenant_id,
        booking_id=booking.id,
        status=REVIEW_STATUS_NO_SHOW,
    )
    db.add(review)
    await db.flush()
    return review


# ── Admin actions ──────────────────────────────────────────────────


async def approve_review(
    db: AsyncSession,
    *,
    review: BookingReview,
    grade: int,
    grade_notes: str | None,
    admin: AdminUser,
) -> BookingReview:
    """Move pending → approved, snapshot final times + hours, then
    trigger quality-score recompute on the volunteer's Contact.
    """
    if review.status not in (REVIEW_STATUS_PENDING, REVIEW_STATUS_NO_SHOW):
        raise ReviewImmutableError(
            f"Cannot approve review in status={review.status}; unlock first."
        )
    if not (1 <= grade <= 5):
        raise ValueError("grade must be between 1 and 5")

    # Reconstruct fresh if the review was created without segments
    # (no_show that admin flipped to pending then approved).
    if not review.segments:
        booking = (
            await db.execute(select(Booking).where(Booking.id == review.booking_id))
        ).scalar_one()
        slot = (
            await db.execute(
                select(SpecificDateSlot).where(
                    SpecificDateSlot.id == booking.event_slot_id
                )
            )
        ).scalar_one()
        review.segments = await reconstruct_segments_from_audit_log(
            db, booking=booking
        )
        slot_start = await _slot_start_utc(db, slot, booking.tenant_id)
        early_min = await _get_setting_int(
            db, booking.tenant_id, "early_checkin_credit_minutes",
            DEFAULT_EARLY_CHECKIN_CREDIT_MINUTES,
        )
        review.total_hours = compute_total_hours(
            review.segments, slot_start, early_min
        )
        if review.segments:
            review.final_check_in_at = _parse_iso(review.segments[0]["in"])
            review.final_check_out_at = _parse_iso(review.segments[-1]["out"])

    review.status = REVIEW_STATUS_APPROVED
    review.grade = grade
    review.grade_notes = grade_notes
    review.reviewed_by_admin_id = admin.id
    review.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    # Side effect 1: recompute the volunteer's historical quality score.
    booking = (
        await db.execute(select(Booking).where(Booking.id == review.booking_id))
    ).scalar_one()
    await recompute_quality_score_for_contact(
        db, tenant_id=booking.tenant_id, contact_id=booking.contact_id
    )

    # Side effect 2 (Phase 5): run the recognition engine for this
    # volunteer so any newly-satisfied milestones/badges land + their
    # opt-in SMS dispatches happen synchronously inside the transaction.
    contact = (
        await db.execute(select(Contact).where(Contact.id == booking.contact_id))
    ).scalar_one()
    from app.services.recognition_engine import evaluate_and_grant_for_contact
    await evaluate_and_grant_for_contact(
        db,
        contact=contact,
        tenant_id=booking.tenant_id,
        triggering_review=review,
    )
    await db.flush()
    return review


async def skip_review(
    db: AsyncSession,
    *,
    review: BookingReview,
    admin: AdminUser,
    notes: str | None = None,
) -> BookingReview:
    """Decision #26 — admin marks as 'skipped' (no grade). Counts as
    completed history but doesn't pollute grade-based metrics."""
    if review.status not in (REVIEW_STATUS_PENDING, REVIEW_STATUS_NO_SHOW):
        raise ReviewImmutableError(
            f"Cannot skip review in status={review.status}; unlock first."
        )
    review.status = REVIEW_STATUS_SKIPPED
    review.reviewed_by_admin_id = admin.id
    review.reviewed_at = datetime.now(timezone.utc)
    if notes:
        review.grade_notes = notes
    await db.flush()
    return review


async def flip_no_show_to_pending(
    db: AsyncSession, *, review: BookingReview, admin: AdminUser
) -> BookingReview:
    """Admin found a check-in retroactively; revert no_show → pending so
    they can grade properly."""
    if review.status != REVIEW_STATUS_NO_SHOW:
        raise ReviewImmutableError(
            f"flip_no_show only valid from status=no_show; got {review.status}"
        )
    review.status = REVIEW_STATUS_PENDING
    review.reviewed_at = None
    review.reviewed_by_admin_id = None
    await db.flush()
    return review


# ── Unlock policy (decision #16) ───────────────────────────────────


def can_unlock_review(
    review: BookingReview,
    slot: SpecificDateSlot,
    admin: AdminUser,
    tenant_timezone: str | None = None,
) -> bool:
    """SUPER_ADMIN always; OWNER unlimited within 24h of slot.end_at."""
    if admin.role == AdminRole.SUPER_ADMIN:
        return True
    if admin.role == AdminRole.OWNER:
        import pytz
        tz = pytz.timezone(tenant_timezone or "America/New_York")
        end_at = tz.localize(
            datetime.combine(slot.date, slot.end_time)
        ).astimezone(timezone.utc)
        return (datetime.now(timezone.utc) - end_at) < timedelta(hours=24)
    return False


async def unlock_review(
    db: AsyncSession, *, review_id: uuid.UUID, admin: AdminUser
) -> BookingReview:
    """Flip an approved review back to pending atomically. Bumps
    unlock_count + records who/when. Also emits an EVENT_REVIEW_UNLOCKED
    audit row (decision #31) for full chronological history."""
    result = await db.execute(
        update(BookingReview)
        .where(
            BookingReview.id == review_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
        )
        .values(
            status=REVIEW_STATUS_PENDING,
            unlocked_at=func.now(),
            unlocked_by_admin_id=admin.id,
            unlock_count=BookingReview.unlock_count + 1,
        )
    )
    if (result.rowcount or 0) == 0:
        raise ReviewImmutableError(
            f"Review {review_id} is not in 'approved' status (already unlocked or never approved)"
        )

    # Audit row — preserves full chronological unlock history.
    db.add(
        AgentCallLog(
            tenant_id=admin.tenant_id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_REVIEW_UNLOCKED,
            source=AGENT_ENGAGEMENT,
            destination=AGENT_ENGAGEMENT,
            decision_reason="admin_unlocked_review",
            payload={
                "booking_review_id": str(review_id),
                "prior_status": REVIEW_STATUS_APPROVED,
                "admin_user_id": str(admin.id),
                "admin_role": admin.role.value,
            },
        )
    )
    await db.flush()
    refreshed = await db.execute(
        select(BookingReview).where(BookingReview.id == review_id)
    )
    return refreshed.scalar_one()


# ── Quality-score recompute (decision #24) ─────────────────────────


async def recompute_quality_score_for_contact(
    db: AsyncSession, *, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> None:
    """Decay-weighted average over last N approved grades. Cold-start
    contacts (no approved reviews) get NULL; targeting layer treats
    NULL as neutral."""
    n_setting = await _get_setting_int(
        db, tenant_id, "quality_recent_n", DEFAULT_QUALITY_RECENT_N
    )

    # Get recent approved reviews' grades.
    grades_result = await db.execute(
        select(BookingReview.grade)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            Booking.contact_id == contact_id,
            BookingReview.tenant_id == tenant_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
            BookingReview.grade.is_not(None),
        )
        .order_by(BookingReview.reviewed_at.desc())
        .limit(n_setting)
    )
    grades: list[int] = [g[0] for g in grades_result.all() if g[0] is not None]
    count_result = await db.execute(
        select(func.count())
        .select_from(BookingReview)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            Booking.contact_id == contact_id,
            BookingReview.tenant_id == tenant_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
        )
    )
    approved_count = int(count_result.scalar() or 0)

    if not grades:
        # Cold-start — nothing to compute. Still update approved_reviews_count.
        await db.execute(
            update(Contact)
            .where(Contact.id == contact_id)
            .values(
                historical_quality_score=None,
                historical_quality_updated_at=datetime.now(timezone.utc),
                approved_reviews_count=approved_count,
            )
        )
        return

    # Decay weights: most recent gets weight 1.0; each step back -10%.
    weights = []
    for i in range(len(grades)):
        w = 1.0 * (0.9 ** i)
        weights.append(w)
    weighted_sum = sum(g * w for g, w in zip(grades, weights))
    weight_total = sum(weights)
    score = Decimal(weighted_sum / weight_total).quantize(Decimal("0.01"))

    await db.execute(
        update(Contact)
        .where(Contact.id == contact_id)
        .values(
            historical_quality_score=score,
            historical_quality_updated_at=datetime.now(timezone.utc),
            approved_reviews_count=approved_count,
        )
    )
    logger.info(
        "recompute_quality_score contact=%s n=%d score=%s",
        contact_id, len(grades), score,
    )
