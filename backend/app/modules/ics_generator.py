"""RFC 5545-compliant ICS calendar invite generator.

Supports three operations:
- New booking: METHOD:REQUEST, SEQUENCE:0
- Reschedule: METHOD:REQUEST, SEQUENCE:N+1
- Cancellation: METHOD:CANCEL, SEQUENCE:N+1
"""

import uuid
from datetime import datetime

import pytz
from icalendar import Calendar, Event, vText

from app.core.config import settings


def _build_uid(booking_id: uuid.UUID) -> str:
    return f"booking-{booking_id}@{settings.business_domain}"


def generate_new_booking_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
) -> bytes:
    """Generate ICS for a new booking (METHOD:REQUEST, SEQUENCE:0)."""
    return _build_ics(
        booking_id=booking_id,
        summary=summary,
        description=description,
        start=start,
        end=end,
        method="REQUEST",
        status="CONFIRMED",
        sequence=0,
    )


def generate_reschedule_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    sequence: int,
) -> bytes:
    """Generate ICS for a rescheduled booking (METHOD:REQUEST, SEQUENCE:N+1)."""
    return _build_ics(
        booking_id=booking_id,
        summary=summary,
        description=description,
        start=start,
        end=end,
        method="REQUEST",
        status="CONFIRMED",
        sequence=sequence,
    )


def generate_cancellation_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    sequence: int,
) -> bytes:
    """Generate ICS for a cancelled booking (METHOD:CANCEL, SEQUENCE:N+1)."""
    return _build_ics(
        booking_id=booking_id,
        summary=summary,
        description=description,
        start=start,
        end=end,
        method="CANCEL",
        status="CANCELLED",
        sequence=sequence,
    )


def _build_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    method: str,
    status: str,
    sequence: int,
) -> bytes:
    """Build an ICS file with the given parameters."""
    tz = pytz.timezone(settings.business_timezone)

    cal = Calendar()
    cal.add("prodid", f"-//{settings.business_name}//Booking System//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", method)

    event = Event()
    event.add("uid", _build_uid(booking_id))
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstart", start.astimezone(tz) if start.tzinfo else tz.localize(start))
    event.add("dtend", end.astimezone(tz) if end.tzinfo else tz.localize(end))
    event.add("dtstamp", datetime.now(tz))
    event.add("sequence", sequence)
    event.add("status", status)
    event["organizer"] = vText(f"MAILTO:bookings@{settings.business_domain}")

    cal.add_component(event)
    return cal.to_ical()
