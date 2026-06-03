"""Phase 5 — recognition (milestone / badge / award) engine.

Owns:
  - metric evaluators: hours, events_completed, service_count, avg_grade_over_last_n
  - scope-aware dedup: lifetime / per_event / per_period (decision #27)
  - period_key derivation (month / quarter / year)
  - manual grant helper
  - congratulatory SMS dispatch (opt-in per tenant)

Run order on review approval:
  1. Recompute contact's historical_quality_score (already happens in
     booking_review.approve_review — separate concern).
  2. For every active definition with auto_criteria, evaluate the criterion
     against the contact's aggregates.
  3. For each newly-satisfied definition, INSERT ... ON CONFLICT DO NOTHING
     (the partial unique indexes enforce per-scope dedup).
  4. For each newly-inserted recognition row, fire the congratulatory SMS
     if the tenant has opted in.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.award_definition import (
    AWARD_SCOPE_LIFETIME,
    AWARD_SCOPE_PER_EVENT,
    AWARD_SCOPE_PER_PERIOD,
    AwardDefinition,
)
from app.models.booking import Booking, BookingStatus
from app.models.booking_review import (
    REVIEW_STATUS_APPROVED,
    BookingReview,
)
from app.models.contact import Contact
from app.models.volunteer_recognition import VolunteerRecognition

logger = get_logger("recognition_engine")


# ── Period-key derivation ──────────────────────────────────────────


def derive_period_key(period_unit: str | None, when: datetime) -> str | None:
    """Decision #27 — render a stable string per period.

    month   → 'YYYY-MM'
    quarter → 'YYYY-Qn'  (n = 1..4)
    year    → 'YYYY'
    """
    if period_unit is None:
        return None
    when_utc = when.astimezone(timezone.utc) if when.tzinfo else when
    if period_unit == "month":
        return when_utc.strftime("%Y-%m")
    if period_unit == "quarter":
        q = (when_utc.month - 1) // 3 + 1
        return f"{when_utc.year}-Q{q}"
    if period_unit == "year":
        return f"{when_utc.year}"
    return None


# ── Metric evaluators ──────────────────────────────────────────────


async def _sum_approved_hours(
    db: AsyncSession, *, contact_id: uuid.UUID, tenant_id: uuid.UUID
) -> float:
    """Total approved-review hours across this volunteer's history."""
    result = await db.execute(
        select(func.coalesce(func.sum(BookingReview.total_hours), 0))
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            BookingReview.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
            BookingReview.total_hours.is_not(None),
        )
    )
    return float(result.scalar() or 0)


async def _count_approved_reviews(
    db: AsyncSession, *, contact_id: uuid.UUID, tenant_id: uuid.UUID
) -> int:
    """Count of approved reviews — events_completed metric."""
    result = await db.execute(
        select(func.count())
        .select_from(BookingReview)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            BookingReview.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
        )
    )
    return int(result.scalar() or 0)


async def _count_service(
    db: AsyncSession,
    *,
    contact_id: uuid.UUID,
    tenant_id: uuid.UUID,
    service_id: uuid.UUID,
) -> int:
    """How many approved reviews involved this appointment_type?

    Phase 5 simplification: counts approved reviews whose booking's
    *planned* appointment_type matches (i.e. booking.appointment_type_id).
    Phase 6+ could refine to count via booking_service_log when needed
    for fine-grained "100 hours of Driving" milestones.
    """
    result = await db.execute(
        select(func.count())
        .select_from(BookingReview)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            BookingReview.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            Booking.appointment_type_id == service_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
        )
    )
    return int(result.scalar() or 0)


async def _avg_grade_over_last_n(
    db: AsyncSession,
    *,
    contact_id: uuid.UUID,
    tenant_id: uuid.UUID,
    n: int,
) -> float | None:
    """Mean of the most recent N approved grades. Returns None if
    fewer than N reviews — we don't pre-fire criteria on cold-start
    volunteers."""
    rows = await db.execute(
        select(BookingReview.grade)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .where(
            BookingReview.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            BookingReview.status == REVIEW_STATUS_APPROVED,
            BookingReview.grade.is_not(None),
        )
        .order_by(BookingReview.reviewed_at.desc())
        .limit(n)
    )
    grades = [int(g[0]) for g in rows.all() if g[0] is not None]
    if len(grades) < n:
        return None
    return sum(grades) / len(grades)


async def evaluate_criterion(
    db: AsyncSession,
    *,
    contact: Contact,
    tenant_id: uuid.UUID,
    criterion: dict | None,
) -> bool:
    """Return True if the contact currently satisfies the criterion.

    Unknown metric → False (silently). Missing thresholds → False.
    """
    if not criterion or not isinstance(criterion, dict):
        return False
    metric = criterion.get("metric")
    try:
        if metric == "hours":
            threshold = float(criterion.get("threshold", 0))
            total = await _sum_approved_hours(
                db, contact_id=contact.id, tenant_id=tenant_id
            )
            return total >= threshold
        if metric == "events_completed":
            threshold = int(criterion.get("threshold", 0))
            count = await _count_approved_reviews(
                db, contact_id=contact.id, tenant_id=tenant_id
            )
            return count >= threshold
        if metric == "service_count":
            service_id_raw = criterion.get("service_id")
            if not service_id_raw:
                return False
            try:
                service_id = uuid.UUID(str(service_id_raw))
            except ValueError:
                return False
            threshold = int(criterion.get("threshold", 0))
            count = await _count_service(
                db,
                contact_id=contact.id,
                tenant_id=tenant_id,
                service_id=service_id,
            )
            return count >= threshold
        if metric == "avg_grade_over_last_n":
            n = int(criterion.get("n", 10))
            threshold = float(criterion.get("threshold", 0))
            avg = await _avg_grade_over_last_n(
                db, contact_id=contact.id, tenant_id=tenant_id, n=n
            )
            return avg is not None and avg >= threshold
    except (TypeError, ValueError):
        return False
    return False


# ── Auto-grant on review approval ──────────────────────────────────


async def evaluate_and_grant_for_contact(
    db: AsyncSession,
    *,
    contact: Contact,
    tenant_id: uuid.UUID,
    triggering_review: BookingReview | None = None,
) -> list[VolunteerRecognition]:
    """Run the engine for one contact. Returns the recognition rows
    newly inserted (skipping ones that already exist via the partial
    unique indexes).

    Idempotent — re-running with no new data inserts nothing.
    """
    defs_result = await db.execute(
        select(AwardDefinition).where(
            AwardDefinition.tenant_id == tenant_id,
            AwardDefinition.is_active.is_(True),
            AwardDefinition.auto_criteria.is_not(None),
        )
    )
    definitions = list(defs_result.scalars().all())
    if not definitions:
        return []

    newly_inserted: list[VolunteerRecognition] = []
    triggering_slot_id: uuid.UUID | None = None
    if triggering_review is not None:
        # Resolve the slot for per_event scope grants.
        booking_q = await db.execute(
            select(Booking).where(Booking.id == triggering_review.booking_id)
        )
        booking = booking_q.scalar_one_or_none()
        if booking is not None:
            triggering_slot_id = booking.event_slot_id

    now_utc = datetime.now(timezone.utc)
    for definition in definitions:
        satisfied = await evaluate_criterion(
            db,
            contact=contact,
            tenant_id=tenant_id,
            criterion=definition.auto_criteria,
        )
        if not satisfied:
            continue

        # Build the scope-aware key columns.
        period_key: str | None = None
        earned_via_slot_id: uuid.UUID | None = None
        if definition.uniqueness_scope == AWARD_SCOPE_PER_PERIOD:
            period_key = derive_period_key(definition.period_unit, now_utc)
        elif definition.uniqueness_scope == AWARD_SCOPE_PER_EVENT:
            earned_via_slot_id = triggering_slot_id
            if earned_via_slot_id is None:
                # per_event grants need a slot context — skip.
                continue

        new_id = uuid.uuid4()
        stmt = (
            pg_insert(VolunteerRecognition.__table__)
            .values(
                id=new_id,
                tenant_id=tenant_id,
                contact_id=contact.id,
                definition_id=definition.id,
                earned_at=now_utc,
                earned_via_review_id=triggering_review.id if triggering_review else None,
                earned_via_slot_id=earned_via_slot_id,
                period_key=period_key,
            )
            .on_conflict_do_nothing()
        )
        result = await db.execute(stmt)
        if (result.rowcount or 0) > 0:
            row = (
                await db.execute(
                    select(VolunteerRecognition).where(
                        VolunteerRecognition.id == new_id
                    )
                )
            ).scalar_one()
            newly_inserted.append(row)
            logger.info(
                "Granted recognition: contact=%s definition=%s scope=%s",
                contact.id, definition.id, definition.uniqueness_scope,
            )

    if newly_inserted:
        await db.flush()
        for row in newly_inserted:
            await _maybe_dispatch_congratulations(
                db, contact=contact, recognition=row
            )
    return newly_inserted


# ── Congratulatory SMS dispatch ────────────────────────────────────


async def _tenant_recognition_sms_enabled(
    db: AsyncSession, tenant_id: uuid.UUID
) -> bool:
    """Per-tenant opt-in (default OFF — conservative per the plan).

    SystemSetting key: `recognition_congrats_enabled`. Truthy values:
    '1', 'true', 'on', 'yes' (case-insensitive). Defaults FALSE.
    """
    from app.models.system_setting import SystemSetting

    row = (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key == "recognition_congrats_enabled",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    val = (row.value or "").strip().lower()
    return val in ("1", "true", "on", "yes")


async def _maybe_dispatch_congratulations(
    db: AsyncSession,
    *,
    contact: Contact,
    recognition: VolunteerRecognition,
) -> None:
    """Send the volunteer a congratulatory SMS if the tenant has opted
    in. Failure to send is logged but doesn't roll back the grant."""
    if not await _tenant_recognition_sms_enabled(db, contact.tenant_id):
        return

    # Resolve the definition for variable substitution.
    definition = (
        await db.execute(
            select(AwardDefinition).where(
                AwardDefinition.id == recognition.definition_id
            )
        )
    ).scalar_one()

    from app.prompts.conversation import _get_prompt, PROMPT_KEYS
    from app.services.sms import send_sms
    from app.models.tenant import Tenant

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == contact.tenant_id))
    ).scalar_one()

    template = await _get_prompt(
        db,
        "prompt_recognition_congratulations",
        PROMPT_KEYS["prompt_recognition_congratulations"],
        tenant_id=contact.tenant_id,
    )
    body = template.format(
        volunteer_name=contact.name or contact.phone,
        award_label=definition.label,
        award_description=definition.description or "",
    )
    if not contact.phone:
        return
    try:
        await send_sms(to=contact.phone, body=body, tenant=tenant)
    except Exception:
        logger.exception(
            "Failed to send recognition SMS to contact=%s", contact.id
        )


# ── Manual grant ───────────────────────────────────────────────────


async def manual_grant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    definition_id: uuid.UUID,
    granted_by_admin_id: uuid.UUID,
    earned_via_slot_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> VolunteerRecognition | None:
    """Admin manually grants a recognition (e.g. Volunteer of the Month
    award). For per_event scope, caller must pass earned_via_slot_id.
    For per_period scope, period_key is derived from NOW().

    Returns None if the partial unique index rejects (already granted).
    """
    definition = (
        await db.execute(
            select(AwardDefinition).where(
                AwardDefinition.id == definition_id,
                AwardDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise ValueError("award definition not found for tenant")

    now_utc = datetime.now(timezone.utc)
    period_key: str | None = None
    if definition.uniqueness_scope == AWARD_SCOPE_PER_PERIOD:
        period_key = derive_period_key(definition.period_unit, now_utc)
    elif definition.uniqueness_scope == AWARD_SCOPE_PER_EVENT:
        if earned_via_slot_id is None:
            raise ValueError(
                "per_event recognitions require earned_via_slot_id"
            )

    new_id = uuid.uuid4()
    stmt = (
        pg_insert(VolunteerRecognition.__table__)
        .values(
            id=new_id,
            tenant_id=tenant_id,
            contact_id=contact_id,
            definition_id=definition.id,
            earned_at=now_utc,
            earned_via_review_id=None,
            earned_via_slot_id=earned_via_slot_id,
            period_key=period_key,
            granted_by_admin_id=granted_by_admin_id,
            notes=notes,
        )
        .on_conflict_do_nothing()
    )
    result = await db.execute(stmt)
    if (result.rowcount or 0) == 0:
        return None

    row = (
        await db.execute(
            select(VolunteerRecognition).where(VolunteerRecognition.id == new_id)
        )
    ).scalar_one()

    # Dispatch SMS for manual grants too (admin-initiated still triggers
    # the volunteer celebration when tenant has opted in).
    contact = (
        await db.execute(select(Contact).where(Contact.id == contact_id))
    ).scalar_one()
    await _maybe_dispatch_congratulations(db, contact=contact, recognition=row)
    return row
