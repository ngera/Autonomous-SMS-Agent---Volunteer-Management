import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking
from app.models.contact import Contact
from app.modules.ics_generator import (
    generate_cancellation_ics,
    generate_new_booking_ics,
    generate_reschedule_ics,
)

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar-ics"])

ICS_CONTENT_TYPE = "text/calendar; charset=utf-8"


async def _get_booking_context(
    booking_id: uuid.UUID, db: AsyncSession
) -> tuple[Booking, str, str]:
    """Load booking with summary and description for ICS generation."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Get appointment type name
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == booking.appointment_type_id)
    )
    appt_type = appt_result.scalar_one_or_none()
    appt_name = appt_type.name if appt_type else "Appointment"

    # Get contact name
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == booking.contact_phone)
    )
    contact = contact_result.scalar_one_or_none()
    contact_name = contact.name if contact and contact.name else booking.contact_phone

    summary = f"{appt_name} — {contact_name}"
    description = (
        f"Phone: {booking.contact_phone} | "
        f"Price: £{booking.price_at_booking:.2f} | "
        f"Booked via SMS"
    )

    return booking, summary, description


@router.get("/{booking_id}/new.ics")
async def get_new_booking_ics(booking_id: uuid.UUID):
    """Serve new booking ICS file. No auth — UUID is the security token."""
    async with async_session_factory() as db:
        booking, summary, description = await _get_booking_context(booking_id, db)

        appt_result = await db.execute(
            select(AppointmentType).where(
                AppointmentType.id == booking.appointment_type_id
            )
        )
        appt_type = appt_result.scalar_one_or_none()
        duration = appt_type.duration_minutes if appt_type else 60

        ics_data = generate_new_booking_ics(
            booking_id=booking.id,
            summary=summary,
            description=description,
            start=booking.scheduled_at,
            end=booking.scheduled_at + timedelta(minutes=duration),
        )

    return Response(
        content=ics_data,
        media_type=ICS_CONTENT_TYPE,
        headers={"Content-Disposition": "attachment; filename=appointment.ics"},
    )


@router.get("/{booking_id}/update.ics")
async def get_update_ics(booking_id: uuid.UUID):
    """Serve reschedule ICS file."""
    async with async_session_factory() as db:
        booking, summary, description = await _get_booking_context(booking_id, db)

        appt_result = await db.execute(
            select(AppointmentType).where(
                AppointmentType.id == booking.appointment_type_id
            )
        )
        appt_type = appt_result.scalar_one_or_none()
        duration = appt_type.duration_minutes if appt_type else 60

        ics_data = generate_reschedule_ics(
            booking_id=booking.id,
            summary=summary,
            description=description,
            start=booking.scheduled_at,
            end=booking.scheduled_at + timedelta(minutes=duration),
            sequence=booking.ics_sequence,
        )

    return Response(
        content=ics_data,
        media_type=ICS_CONTENT_TYPE,
        headers={"Content-Disposition": "attachment; filename=appointment.ics"},
    )


@router.get("/{booking_id}/cancel.ics")
async def get_cancel_ics(booking_id: uuid.UUID):
    """Serve cancellation ICS file."""
    async with async_session_factory() as db:
        booking, summary, description = await _get_booking_context(booking_id, db)

        appt_result = await db.execute(
            select(AppointmentType).where(
                AppointmentType.id == booking.appointment_type_id
            )
        )
        appt_type = appt_result.scalar_one_or_none()
        duration = appt_type.duration_minutes if appt_type else 60

        ics_data = generate_cancellation_ics(
            booking_id=booking.id,
            summary=summary,
            description=description,
            start=booking.scheduled_at,
            end=booking.scheduled_at + timedelta(minutes=duration),
            sequence=booking.ics_sequence,
        )

    return Response(
        content=ics_data,
        media_type=ICS_CONTENT_TYPE,
        headers={"Content-Disposition": "attachment; filename=appointment.ics"},
    )
