"""Recurring appointment intelligence.

Calculates personalised recurrence intervals per customer + appointment type
using median-based outlier removal and confidence-weighted blending.

Spec Section 11:
- 0-2 bookings: 100% admin default
- 3 bookings: 33% personal / 67% default
- 4 bookings: 55% personal / 45% default
- 5 bookings: 77% personal / 23% default
- 6+ bookings: 100% personal
"""

import statistics
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.pattern import CustomerAppointmentPattern, PatternConfidence

logger = get_logger("pattern")

# Confidence weights: (personal_weight, default_weight)
CONFIDENCE_WEIGHTS = {
    0: (0.0, 1.0),
    1: (0.0, 1.0),
    2: (0.0, 1.0),
    3: (0.33, 0.67),
    4: (0.55, 0.45),
    5: (0.77, 0.23),
}


async def recalculate_pattern(
    db: AsyncSession,
    contact_phone: str,
    appointment_type_id: str,
    tenant_id: uuid.UUID | None = None,
) -> CustomerAppointmentPattern | None:
    """Recalculate the recurrence pattern for a customer + appointment type.

    Called after a booking is marked COMPLETED.
    """
    type_uuid = uuid.UUID(appointment_type_id) if isinstance(appointment_type_id, str) else appointment_type_id

    # Get all completed bookings sorted by date
    bookings_query = (
        select(Booking)
        .where(
            Booking.contact_phone == contact_phone,
            Booking.appointment_type_id == type_uuid,
            Booking.status == BookingStatus.COMPLETED,
        )
        .order_by(Booking.scheduled_at)
    )
    if tenant_id:
        bookings_query = bookings_query.where(Booking.tenant_id == tenant_id)
    result = await db.execute(bookings_query)
    bookings = result.scalars().all()
    completed_count = len(bookings)

    # Default interval: 4 weeks. The per-type override has been removed.
    admin_default_days = 28

    # Get or create pattern record
    pattern_query = select(CustomerAppointmentPattern).where(
        CustomerAppointmentPattern.contact_phone == contact_phone,
        CustomerAppointmentPattern.appointment_type_id == type_uuid,
    )
    if tenant_id:
        pattern_query = pattern_query.where(CustomerAppointmentPattern.tenant_id == tenant_id)
    pattern_result = await db.execute(pattern_query)
    pattern = pattern_result.scalar_one_or_none()

    if not pattern:
        # Resolve contact_id from phone
        from app.models.contact import Contact
        contact_query = select(Contact.id).where(Contact.phone == contact_phone)
        if tenant_id:
            contact_query = contact_query.where(Contact.tenant_id == tenant_id)
        contact_result = await db.execute(contact_query)
        contact_id = contact_result.scalar_one_or_none()

        pattern = CustomerAppointmentPattern(
            contact_phone=contact_phone,
            contact_id=contact_id,
            tenant_id=tenant_id,
            appointment_type_id=type_uuid,
        )
        db.add(pattern)

    # If manual override is set, skip algorithm
    if pattern.manual_override_days is not None:
        pattern.completed_booking_count = completed_count
        pattern.admin_default_days = admin_default_days
        pattern.blended_interval_days = pattern.manual_override_days
        pattern.last_calculated_at = datetime.now(timezone.utc)
        pattern.next_due_date = _calculate_next_due(bookings, pattern.manual_override_days)
        await db.flush()
        return pattern

    # Calculate gaps between consecutive bookings
    calculated_interval = None
    outliers_removed = 0
    confidence = PatternConfidence.DEFAULT

    if completed_count >= 2:
        gaps = []
        for i in range(1, len(bookings)):
            gap = (bookings[i].scheduled_at - bookings[i - 1].scheduled_at).days
            if gap > 0:
                gaps.append(gap)

        if gaps:
            calculated_interval, outliers_removed = _calculate_interval(gaps)

    # Determine confidence level
    if completed_count >= 6:
        confidence = PatternConfidence.PERSONAL
    elif completed_count >= 3:
        confidence = PatternConfidence.EMERGING
    else:
        confidence = PatternConfidence.DEFAULT

    # Blend personal and default intervals
    if calculated_interval is not None and completed_count >= 3:
        weights = CONFIDENCE_WEIGHTS.get(
            min(completed_count, 5),
            (1.0, 0.0) if completed_count >= 6 else (0.0, 1.0),
        )
        if completed_count >= 6:
            weights = (1.0, 0.0)

        blended = (
            calculated_interval * weights[0]
            + admin_default_days * weights[1]
        )
    else:
        blended = admin_default_days

    # Update pattern
    pattern.completed_booking_count = completed_count
    pattern.calculated_interval_days = calculated_interval
    pattern.blended_interval_days = round(blended, 2)
    pattern.admin_default_days = admin_default_days
    pattern.confidence = confidence
    pattern.outliers_removed = outliers_removed
    pattern.last_calculated_at = datetime.now(timezone.utc)
    pattern.next_due_date = _calculate_next_due(bookings, blended)

    await db.flush()

    logger.info(
        "Pattern recalculated for %s / %s: %d bookings, interval=%.1f days, confidence=%s",
        contact_phone, appointment_type_id, completed_count, blended, confidence.value,
    )

    return pattern


def _calculate_interval(gaps: list[int]) -> tuple[float, int]:
    """Calculate mean interval with outlier removal.

    1. Calculate median of gaps
    2. Remove outliers > 2x median
    3. If fewer than 2 gaps remain, revert to original
    4. Return mean of remaining gaps
    """
    if not gaps:
        return 0.0, 0

    median = statistics.median(gaps)
    threshold = median * 2

    filtered = [g for g in gaps if g <= threshold]
    outliers_removed = len(gaps) - len(filtered)

    # If too few remain, revert to original
    if len(filtered) < 2:
        filtered = gaps
        outliers_removed = 0

    mean_interval = statistics.mean(filtered)
    return round(mean_interval, 2), outliers_removed


def _calculate_next_due(bookings: list, interval_days: float) -> date | None:
    """Calculate next due date from the last completed booking."""
    if not bookings:
        return None

    last_booking = bookings[-1]
    last_date = last_booking.scheduled_at
    if hasattr(last_date, "date"):
        last_date = last_date.date()
    elif isinstance(last_date, datetime):
        last_date = last_date.date()

    return last_date + timedelta(days=int(interval_days))
