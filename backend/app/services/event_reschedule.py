"""Cascade slot date/time changes to bookings, volunteers, and campaigns.

When an admin edits a SpecificDateSlot's date / start_time / end_time,
all signups for that event need to follow the move and the recruitment
campaign (if active) needs its planned waves recomputed against the
new event date. Without this cascade, the implicit-date-match between
``Booking.scheduled_at`` and ``SpecificDateSlot.date`` silently breaks:
bookings get orphaned at the old date and the slot's new date shows an
empty roster.

This module is the single owner of that cascade. The slot-edit endpoint
calls ``cascade_slot_reschedule()`` inline (so the DB is internally
consistent before the response returns), then ``schedule_reconfirmation_sms()``
as a fire-and-forget background task to text affected volunteers and
notify the admin.

See design_decisions.md #19 for the reasoning behind the FK + cascade
shape vs. alternatives (pure date-cascade, soft-delete-and-recreate).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)
from app.models.tenant import Tenant
from app.services.sms import send_sms

logger = get_logger("event_reschedule")

# Volunteer has this many hours to reply YES / STOP before we treat the
# pending reconfirmation as expired. 48h matches the recruitment wave
# cooldown window in targeting.py — same rule of thumb.
RECONFIRMATION_WINDOW_HOURS = 48

# Strong-ref set for background tasks per design_decisions.md #4.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _schedule_background(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    task.add_done_callback(_log_background_task_result)


def _log_background_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "Event-reschedule background task raised: %s",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


def slot_datetime_changed(
    old_date: date,
    old_start: time | None,
    old_end: time | None,
    new_date: date | None,
    new_start: time | None,
    new_end: time | None,
) -> bool:
    """Return True if any of date / start_time / end_time changed.

    Caller passes the snapshot taken BEFORE applying updates so we can
    avoid triggering the cascade on no-op edits (e.g. label-only).
    """
    if new_date is not None and new_date != old_date:
        return True
    if new_start is not None and new_start != old_start:
        return True
    if new_end is not None and new_end != old_end:
        return True
    return False


def _slot_start_datetime(slot: SpecificDateSlot) -> datetime:
    """Compose ``slot.date`` + ``slot.start_time`` as an aware UTC datetime.

    Mirrors how ``materialize_waves_on_approval`` builds event_dt — keeps
    arithmetic consistent across recruiter and reschedule paths.
    """
    return datetime.combine(
        slot.date,
        slot.start_time or datetime.min.time(),
        tzinfo=timezone.utc,
    )


async def cascade_slot_reschedule(
    db: AsyncSession,
    slot: SpecificDateSlot,
    old_date: date,
    old_start: time | None,
) -> dict:
    """Sync bookings and campaign waves to the slot's new date/time.

    Runs inline with the slot-edit transaction so the API response sees
    a consistent state. Returns a small summary dict for the background
    notifier to consume:

        {
          "slot_id": uuid,
          "tenant_id": uuid,
          "old_dt": datetime,
          "new_dt": datetime,
          "affected_booking_ids": list[uuid],
          "campaign_ids_recalibrated": list[uuid],
        }
    """
    # 1. Compute the timestamp delta. We shift every affected booking by
    #    (new_dt - old_dt) rather than overwriting to the new start
    #    time. This preserves any per-booking timing that may have
    #    differed from the slot's start (rare in this codebase but
    #    cheap to honor).
    old_dt = datetime.combine(
        old_date,
        old_start or datetime.min.time(),
        tzinfo=timezone.utc,
    )
    new_dt = _slot_start_datetime(slot)
    delta = new_dt - old_dt

    affected_booking_ids: list[uuid.UUID] = []
    if delta != timedelta(0):
        bookings_q = await db.execute(
            select(Booking).where(
                Booking.event_slot_id == slot.id,
                Booking.status.in_(
                    [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
                ),
            )
        )
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=RECONFIRMATION_WINDOW_HOURS)
        for b in bookings_q.scalars().all():
            b.scheduled_at = b.scheduled_at + delta
            b.pending_reconfirmation_until = until
            affected_booking_ids.append(b.id)

    # 2. Recalibrate any non-terminal recruitment campaigns tied to this
    #    slot — cancel PLANNED waves and re-materialize from the new
    #    event date. SENT waves are immutable history, left alone.
    campaign_ids_recalibrated: list[uuid.UUID] = []
    campaigns_q = await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.event_slot_id == slot.id,
            RecruitmentCampaign.status.in_(
                [CampaignStatus.ACTIVE, CampaignStatus.PAUSED]
            ),
        )
    )
    campaigns = list(campaigns_q.scalars().all())
    if campaigns and delta != timedelta(0):
        from app.agents.recruiter import executor as recruiter_executor
        for campaign in campaigns:
            # Drop PLANNED waves (their scheduled_at is relative to the
            # old date and may now be in the past or wildly off).
            await db.execute(
                delete(RecruitmentWave).where(
                    RecruitmentWave.campaign_id == campaign.id,
                    RecruitmentWave.status == WaveStatus.PLANNED,
                )
            )
            # Re-materialize against the new event datetime. Wave 1
            # still snaps to now (decision #9), so the next tick will
            # pick up where the cancelled plan left off.
            await recruiter_executor.materialize_waves_on_approval(
                db, campaign, slot
            )
            campaign_ids_recalibrated.append(campaign.id)

    await db.flush()
    return {
        "slot_id": slot.id,
        "tenant_id": slot.tenant_id,
        "old_dt": old_dt,
        "new_dt": new_dt,
        "affected_booking_ids": affected_booking_ids,
        "campaign_ids_recalibrated": campaign_ids_recalibrated,
    }


def _format_when(dt: datetime) -> str:
    """Render a datetime as '2026-06-15 09:00 UTC' for SMS clarity."""
    return dt.strftime("%Y-%m-%d %H:%M") + " UTC"


async def _render_reconfirm_sms(
    contact: Contact, event_label: str, old_dt: datetime, new_dt: datetime
) -> str:
    name_part = ""
    if contact.name:
        name_part = f" {contact.name.split()[0]}"
    return (
        f"Hi{name_part}, the {event_label} you signed up for has moved "
        f"from {_format_when(old_dt)} to {_format_when(new_dt)}. "
        "Reply YES to keep your spot or STOP to cancel."
    )


async def _send_reconfirmation_messages(
    summary: dict,
    event_label: str,
) -> None:
    """Background task: SMS each volunteer + mirror to their conversation
    + post an admin notification summarizing the cascade.

    Opens its own AsyncSession (per design_decisions.md #5 — background
    tasks cannot share the request session). Failures are logged and
    swallowed; one failed SMS must not block the others.
    """
    affected_ids = summary["affected_booking_ids"]
    if not affected_ids and not summary["campaign_ids_recalibrated"]:
        return

    async with async_session_factory() as db:
        tenant = await db.get(Tenant, summary["tenant_id"])
        if tenant is None:
            return

        # Resolve each booking + contact
        bookings_q = await db.execute(
            select(Booking).where(Booking.id.in_(affected_ids))
        )
        for booking in bookings_q.scalars().all():
            contact = await db.get(Contact, booking.contact_id)
            if not contact or not contact.phone:
                continue
            try:
                body = await _render_reconfirm_sms(
                    contact, event_label,
                    summary["old_dt"], summary["new_dt"],
                )
                await send_sms(contact.phone, body, tenant)
                # Mirror into the volunteer's conversation so the in-app
                # views show the outbound message.
                from app.api.announcements import (
                    _append_announcement_to_history,
                )
                try:
                    await _append_announcement_to_history(
                        db, tenant.id, contact.phone, body,
                        datetime.now(timezone.utc),
                    )
                except Exception:
                    logger.exception(
                        "Failed to mirror reconfirmation SMS to "
                        "conversation for booking %s", booking.id,
                    )
            except Exception:
                logger.exception(
                    "Failed to send reconfirmation SMS for booking %s",
                    booking.id,
                )

        # Admin notification summarizing the cascade
        try:
            from app.models.notification import NotificationType
            from app.services.notification import create_notification

            body = (
                f"Event '{event_label}' moved from "
                f"{_format_when(summary['old_dt'])} to "
                f"{_format_when(summary['new_dt'])}. "
                f"{len(affected_ids)} booked volunteer"
                f"{'s' if len(affected_ids) != 1 else ''} were notified "
                "to confirm or opt out. "
                f"{len(summary['campaign_ids_recalibrated'])} active "
                "campaign(s) were recalibrated to the new date."
            )
            await create_notification(
                db=db,
                notification_type=NotificationType.EVENT_RESCHEDULED,
                title=f"Event rescheduled: {event_label}",
                body=body,
                tenant_id=tenant.id,
            )
        except Exception:
            logger.exception(
                "Failed to create EVENT_RESCHEDULED admin notification "
                "for slot %s", summary["slot_id"],
            )

        await db.commit()


def schedule_reconfirmation_sms(summary: dict, event_label: str) -> None:
    """Kick off the SMS fan-out as a background task.

    Wrapped in a strong-ref set so the task can't be GC'd mid-execution
    (design_decisions.md #4). Caller must have committed the slot edit
    transaction first (decision #5) so the background session sees the
    new state.
    """
    _schedule_background(_send_reconfirmation_messages(summary, event_label))
