"""Pending-reconfirmation lifecycle for bookings impacted by event reschedules.

When a slot's date/time moves (see ``event_reschedule.cascade_slot_reschedule``),
each affected booking gets ``pending_reconfirmation_until = now + 48h``. The
volunteer is asked by SMS to reply YES (keep the spot) or STOP (cancel). This
module owns both ends of that loop:

- ``pending_reconfirmations()`` — query for bookings still inside the window.
- ``confirm_booking()`` — clear the flag, refresh ``confirmed_at``, record
  history.
- ``cancel_due_to_reschedule()`` — set status=CANCELLED, record history,
  fire the existing cancellation lifecycle (calendar + SMS).
- ``maybe_handle_reconfirmation_directly()`` — server-side intent router
  (same pattern as design_decisions.md #7). Short-circuits the LLM for
  unambiguous YES / STOP replies when a pending reconfirmation exists.
  The LLM has no value-add for these two trigger words and routinely
  fails to invoke a tool for them; deterministic routing is safer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.booking_history import (
    BookingEventType,
    BookingHistory,
    ChangedBy,
)
from app.models.contact import Contact
from app.models.tenant import Tenant

logger = get_logger("reconfirm")


_CONFIRM_TRIGGERS = {
    "yes", "y", "yep", "yeah", "yup",
    "ok", "okay", "k", "kk",
    "sure", "fine", "confirm", "confirmed",
    "im in", "i'm in", "count me in", "ill be there", "i'll be there",
    "keep it", "keep my spot", "keep my booking",
    "still in", "still coming", "going",
}

_CANCEL_TRIGGERS = {
    "stop", "no", "n", "nope", "cancel", "cant", "can't",
    "wont", "won't", "out", "opt out", "opt-out",
    "remove me", "cancel me", "cancel my booking",
    "im out", "i'm out", "drop me",
}


def _normalize(text: str) -> str:
    """Lowercase, strip whitespace, drop trailing punctuation."""
    cleaned = (text or "").strip().lower()
    while cleaned and cleaned[-1] in ".!?,;:":
        cleaned = cleaned[:-1]
    return cleaned


async def pending_reconfirmations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> list[Booking]:
    """Bookings for this contact whose pending_reconfirmation_until is
    in the future. Ordered by event start time so the soonest reschedule
    surfaces first when multiple are pending."""
    now = datetime.now(timezone.utc)
    q = await db.execute(
        select(Booking)
        .where(
            Booking.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            Booking.pending_reconfirmation_until.isnot(None),
            Booking.pending_reconfirmation_until >= now,
            Booking.status.in_(
                [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
            ),
        )
        .order_by(Booking.scheduled_at.asc())
    )
    return list(q.scalars().all())


async def confirm_booking(db: AsyncSession, booking: Booking) -> None:
    """Volunteer confirmed the rescheduled booking. Clear the pending flag,
    refresh ``confirmed_at``, record history. No external lifecycle is
    needed — the booking simply stays in place at the new date.
    """
    now = datetime.now(timezone.utc)
    previous_status = booking.status
    booking.pending_reconfirmation_until = None
    booking.confirmed_at = now
    # Use RESCHEDULED to flag the audit row, since this confirmation is
    # the closing leg of a reschedule. Keeps history readable: edit →
    # cascade → confirm.
    db.add(
        BookingHistory(
            tenant_id=booking.tenant_id,
            booking_id=booking.id,
            event_type=BookingEventType.RESCHEDULED,
            new_status=booking.status,
            new_scheduled_at=booking.scheduled_at,
            previous_status=previous_status,
            changed_by=ChangedBy.USER_SMS,
            notes="volunteer reconfirmed after event reschedule",
        )
    )
    await db.flush()


async def cancel_due_to_reschedule(
    db: AsyncSession, booking: Booking, tenant: Tenant
) -> None:
    """Volunteer opted out of the rescheduled event. Flip status, write
    history, and fire the existing cancellation lifecycle (calendar
    deletion + cancel SMS). We skip the lifecycle SMS for this path
    because the volunteer literally just texted STOP — re-sending them
    a 'your booking has been cancelled' SMS would be noise.
    """
    previous_status = booking.status
    booking.status = BookingStatus.CANCELLED
    booking.pending_reconfirmation_until = None
    db.add(
        BookingHistory(
            tenant_id=booking.tenant_id,
            booking_id=booking.id,
            event_type=BookingEventType.CANCELLED,
            new_status=BookingStatus.CANCELLED,
            previous_status=previous_status,
            changed_by=ChangedBy.USER_SMS,
            notes="volunteer opted out after event reschedule",
        )
    )
    await db.flush()
    # Reuse the existing cancellation lifecycle (calendar event delete +
    # optional SMS). send_sms_notification=False because the volunteer
    # initiated the cancel — they don't need another SMS confirming it.
    from app.services.booking import process_booking_cancellation
    try:
        await process_booking_cancellation(
            db, booking, tenant, send_sms_notification=False
        )
    except Exception:
        logger.exception(
            "process_booking_cancellation failed for opt-out booking %s",
            booking.id,
        )


async def maybe_handle_reconfirmation_directly(
    db: AsyncSession,
    tenant: Tenant,
    contact: Contact,
    body: str,
) -> str | None:
    """Server-side intent router for YES / STOP replies to a reschedule
    notification. Returns the reply text to send back to the volunteer,
    or None if the message doesn't match a trigger or no pending
    reconfirmation exists. The customer pipeline calls this BEFORE the
    LLM (decision #7 pattern); falls through to the LLM otherwise.
    """
    pending = await pending_reconfirmations(db, tenant.id, contact.id)
    if not pending:
        return None

    normalized = _normalize(body)
    is_confirm = normalized in _CONFIRM_TRIGGERS
    is_cancel = normalized in _CANCEL_TRIGGERS
    if not (is_confirm or is_cancel):
        return None

    # Act on every pending reconfirmation — if a single volunteer has
    # multiple events that got rescheduled, treat a bare YES / STOP as
    # applying to all of them. The reschedule SMS named the event so
    # the volunteer knows; if they want to confirm one and decline
    # another, they'd say so explicitly and we'd fall through to LLM.
    if is_confirm:
        for booking in pending:
            await confirm_booking(db, booking)
        await db.flush()
        events = ", ".join(
            booking.scheduled_at.strftime("%Y-%m-%d %H:%M")
            for booking in pending
        )
        return (
            f"Thanks — you're confirmed for the new time ({events}). "
            "We'll see you there."
        )

    # is_cancel
    for booking in pending:
        await cancel_due_to_reschedule(db, booking, tenant)
    await db.flush()
    return (
        "Got it — you've been removed from the rescheduled event. "
        "Thanks for letting us know."
    )
