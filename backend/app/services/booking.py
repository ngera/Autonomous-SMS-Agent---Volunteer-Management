"""Booking service — orchestrates calendar, SMS, and ICS for booking lifecycle events."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.services.calendar import create_event, delete_event, update_event
from app.services.notification import create_notification
from app.models.notification import NotificationType
from app.services.sms import send_sms

logger = get_logger("booking")


async def find_slot_for_booking(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    scheduled_at: datetime,
    appointment_type_id: uuid.UUID,
) -> SpecificDateSlot | None:
    """Resolve which specific-date slot (if any) a booking belongs to.

    Returns the slot whose ``date`` matches ``scheduled_at`` and whose
    ``service_config`` includes ``appointment_type_id``. Returns None
    for regular-availability bookings (those have no slot link). Used
    by every booking creation path to populate ``Booking.event_slot_id``
    so the slot-edit cascade can find affected bookings by FK.
    """
    booking_date = scheduled_at.date()
    slot_q = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant_id,
            SpecificDateSlot.date == booking_date,
        )
    )
    for slot in slot_q.scalars().all():
        for entry in slot.service_config or []:
            if str(entry.get("appointment_type_id")) == str(appointment_type_id):
                return slot
    return None


async def find_volunteer_overlap(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_booking_id: uuid.UUID | None = None,
) -> tuple[Booking, AppointmentType] | None:
    """Find an active booking for this volunteer that overlaps the given window.

    Two appointments overlap when one starts before the other ends. Status is
    restricted to active (SCHEDULED/RESCHEDULED) so already-cancelled bookings
    don't trigger false positives. Pass ``exclude_booking_id`` when checking
    around an in-flight reschedule so the booking isn't compared against
    itself.
    """
    new_end = scheduled_at + timedelta(minutes=duration_minutes)
    query = (
        select(Booking, AppointmentType)
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .where(
            Booking.tenant_id == tenant_id,
            Booking.contact_id == contact_id,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
            Booking.scheduled_at < new_end,
            (
                Booking.scheduled_at
                + func.make_interval(0, 0, 0, 0, 0, AppointmentType.duration_minutes)
            )
            > scheduled_at,
        )
        .limit(1)
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)
    result = await db.execute(query)
    row = result.first()
    return (row[0], row[1]) if row else None


async def process_booking_creation(db: AsyncSession, booking: Booking, tenant: Tenant, send_sms_notification: bool = True) -> None:
    """After a booking is created: create calendar event, generate ICS URLs, send SMS."""
    # Load appointment type for duration
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == booking.appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        return

    # Load contact name
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == booking.contact_phone)
    )
    contact = contact_result.scalar_one_or_none()
    contact_name = contact.name if contact and contact.name else booking.contact_phone

    end_time = booking.scheduled_at + timedelta(minutes=appt_type.duration_minutes)

    # Create Google Calendar event
    try:
        event_id = await create_event(
            summary=f"{appt_type.name} — {contact_name}",
            description=f"Phone: {booking.contact_phone} | Price: £{booking.price_at_booking:.2f} | Booked via SMS",
            start_time=booking.scheduled_at,
            end_time=end_time,
            tenant=tenant,
        )
        booking.calendar_event_id = event_id
    except Exception as e:
        logger.error("Failed to create calendar event for booking %s: %s", booking.id, e)
        await create_notification(
            db=db,
            notification_type=NotificationType.CALENDAR_ERROR,
            title="Calendar event creation failed",
            body=f"Booking {booking.id} for {booking.contact_phone}: {str(e)}",
            reference_id=booking.id,
            reference_type="booking",
            tenant_id=tenant.id,
        )

    # Generate ICS URLs
    base_url = f"https://{tenant.api_domain}/api/v1/calendar/{booking.id}"
    booking.ics_new_url = f"{base_url}/new.ics"
    booking.ics_update_url = f"{base_url}/update.ics"

    await db.flush()

    # Send SMS confirmation
    if send_sms_notification:
        time_str = booking.scheduled_at.strftime("%A %d %B at %I:%M%p")
        await send_sms(
            to=booking.contact_phone,
            body=(
                f"Your {appt_type.name} is confirmed for {time_str}. "
                f"Price: £{booking.price_at_booking:.2f}. "
                f"Add to your calendar: {booking.ics_new_url}"
            ),
            tenant=tenant,
        )

    # Recruitment attribution: if this booking matches an active campaign's
    # event slot + service AND the contact was in a recent wave's
    # targeted_contact_ids, write a RecruitmentSignup row + bump the wave's
    # signups_attributed counter. Best-effort; failures here must not break
    # the booking write path.
    try:
        await _attribute_to_recruitment_campaign(db, booking)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Recruitment attribution failed for booking %s: %s",
            booking.id, e,
        )


async def _attribute_to_recruitment_campaign(
    db: AsyncSession, booking: Booking
) -> None:
    """Link a new booking to a recruitment campaign + wave when applicable."""
    from app.models.availability import SpecificDateSlot
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
        RecruitmentSignup,
        RecruitmentWave,
        WaveStatus,
    )

    # Find any active/pending campaign for an event slot on this booking's
    # date that includes this service.
    booking_date = booking.scheduled_at.date()
    slot_q = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == booking.tenant_id,
            SpecificDateSlot.date == booking_date,
        )
    )
    slots = list(slot_q.scalars().all())
    matching_slot: SpecificDateSlot | None = None
    for slot in slots:
        for entry in slot.service_config or []:
            if str(entry.get("appointment_type_id")) == str(
                booking.appointment_type_id
            ):
                matching_slot = slot
                break
        if matching_slot:
            break
    if not matching_slot:
        return

    campaign_q = await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == booking.tenant_id,
            RecruitmentCampaign.event_slot_id == matching_slot.id,
            RecruitmentCampaign.status.in_(
                [CampaignStatus.ACTIVE, CampaignStatus.PAUSED]
            ),
        )
    )
    campaign = campaign_q.scalar_one_or_none()
    if not campaign:
        return

    # Find the wave (if any) that targeted this contact for this service.
    contact_id_str = str(booking.contact_id)
    waves_q = await db.execute(
        select(RecruitmentWave).where(
            RecruitmentWave.tenant_id == booking.tenant_id,
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.appointment_type_id == booking.appointment_type_id,
            RecruitmentWave.status == WaveStatus.SENT,
        )
    )
    attributed_wave: RecruitmentWave | None = None
    for wave in waves_q.scalars().all():
        if wave.targeted_contact_ids and contact_id_str in [
            str(x) for x in wave.targeted_contact_ids
        ]:
            attributed_wave = wave
            break

    # Skip if no wave actually messaged this contact (self-driven booking) —
    # attribution should reflect causation, not just coincidence.
    if not attributed_wave:
        return

    signup = RecruitmentSignup(
        tenant_id=booking.tenant_id,
        campaign_id=campaign.id,
        wave_id=attributed_wave.id,
        contact_id=booking.contact_id,
        appointment_type_id=booking.appointment_type_id,
        booking_id=booking.id,
    )
    db.add(signup)
    attributed_wave.signups_attributed = (
        (attributed_wave.signups_attributed or 0) + 1
    )
    await db.flush()
    logger.info(
        "Recruitment signup attributed: campaign=%s wave=%s booking=%s",
        campaign.id, attributed_wave.id, booking.id,
    )


async def process_booking_reschedule(db: AsyncSession, booking: Booking, tenant: Tenant, send_sms_notification: bool = True) -> None:
    """After a reschedule: update calendar event, send SMS + ICS update."""
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == booking.appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        return

    end_time = booking.scheduled_at + timedelta(minutes=appt_type.duration_minutes)

    # Update Google Calendar
    if booking.calendar_event_id:
        try:
            await update_event(
                event_id=booking.calendar_event_id,
                start_time=booking.scheduled_at,
                end_time=end_time,
                tenant=tenant,
            )
        except Exception as e:
            logger.error("Failed to update calendar event: %s", e)

    # Send SMS
    if send_sms_notification:
        time_str = booking.scheduled_at.strftime("%A %d %B at %I:%M%p")
        base_url = f"https://{tenant.api_domain}/api/v1/calendar/{booking.id}"
        await send_sms(
            to=booking.contact_phone,
            body=(
                f"Your appointment has been rescheduled to {time_str}. "
                f"Update your calendar: {base_url}/update.ics"
            ),
            tenant=tenant,
        )


async def process_booking_cancellation(db: AsyncSession, booking: Booking, tenant: Tenant, send_sms_notification: bool = True) -> None:
    """After cancellation: delete calendar event, send SMS + ICS cancel."""
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == booking.appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    appt_name = appt_type.name if appt_type else "appointment"

    # Delete Google Calendar event
    if booking.calendar_event_id:
        try:
            await delete_event(booking.calendar_event_id, tenant=tenant)
        except Exception as e:
            logger.error("Failed to delete calendar event: %s", e)

    # Send SMS
    if send_sms_notification:
        time_str = booking.scheduled_at.strftime("%A %d %B")
        base_url = f"https://{tenant.api_domain}/api/v1/calendar/{booking.id}"
        await send_sms(
            to=booking.contact_phone,
            body=(
                f"Your {appt_name} on {time_str} has been cancelled. "
                f"Remove from your calendar: {base_url}/cancel.ics"
            ),
            tenant=tenant,
        )
