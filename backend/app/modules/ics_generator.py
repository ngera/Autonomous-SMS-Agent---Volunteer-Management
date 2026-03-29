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
from app.models.tenant import Tenant


def _build_uid(booking_id: uuid.UUID, tenant: Tenant | None = None) -> str:
    domain = tenant.business_domain if tenant else settings.business_domain
    return f"booking-{booking_id}@{domain}"


def generate_new_booking_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    tenant: Tenant | None = None,
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
        tenant=tenant,
    )


def generate_reschedule_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    sequence: int,
    tenant: Tenant | None = None,
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
        tenant=tenant,
    )


def generate_cancellation_ics(
    booking_id: uuid.UUID,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    sequence: int,
    tenant: Tenant | None = None,
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
        tenant=tenant,
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
    tenant: Tenant | None = None,
) -> bytes:
    """Build an ICS file with the given parameters."""
    business_name = tenant.business_name if tenant else settings.business_name
    business_timezone = tenant.business_timezone if tenant else settings.business_timezone
    business_domain = tenant.business_domain if tenant else settings.business_domain

    tz = pytz.timezone(business_timezone)

    cal = Calendar()
    cal.add("prodid", f"-//{business_name}//Booking System//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", method)

    event = Event()
    event.add("uid", _build_uid(booking_id, tenant=tenant))
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstart", start.astimezone(tz) if start.tzinfo else tz.localize(start))
    event.add("dtend", end.astimezone(tz) if end.tzinfo else tz.localize(end))
    event.add("dtstamp", datetime.now(tz))
    event.add("sequence", sequence)
    event.add("status", status)
    event["organizer"] = vText(f"MAILTO:bookings@{business_domain}")

    cal.add_component(event)
    return cal.to_ical()
