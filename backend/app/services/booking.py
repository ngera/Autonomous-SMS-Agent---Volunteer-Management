"""Booking service — orchestrates calendar, SMS, and ICS for booking lifecycle events."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking, BookingStatus
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.services.calendar import create_event, delete_event, update_event
from app.services.notification import create_notification
from app.models.notification import NotificationType
from app.services.sms import send_sms

logger = get_logger("booking")


async def process_booking_creation(db: AsyncSession, booking: Booking, tenant: Tenant) -> None:
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


async def process_booking_reschedule(db: AsyncSession, booking: Booking, tenant: Tenant) -> None:
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


async def process_booking_cancellation(db: AsyncSession, booking: Booking, tenant: Tenant) -> None:
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
