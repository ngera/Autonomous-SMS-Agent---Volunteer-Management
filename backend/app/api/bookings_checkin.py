"""Phase 1 admin override endpoints — check-in/check-out via UI + run-sheet.

Kept in a separate module from app/api/bookings.py to keep the
existing file focused and minimize merge risk. Mounted under the
same prefix in main.py.

Endpoints:
  POST /api/v1/bookings/{id}/checkin   — admin UI check-in override
  POST /api/v1/bookings/{id}/checkout  — admin UI check-out override
  GET  /api/v1/bookings/run-sheet/{slot_id} — live roster for one event
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytz
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.base import EVENT_ADMIN_OVERRIDE
from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.agent_call_log import AgentCallLog
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import (
    Booking,
    BookingStatus,
    CHECKIN_SOURCE_ADMIN_OVERRIDE,
    CHECKOUT_SOURCE_ADMIN_OVERRIDE,
)
from app.models.contact import Contact
from app.schemas.booking import BookingResponse

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


class CheckInOverrideRequest(BaseModel):
    """Admin UI override: mark a booking as checked in or out at a
    specific time. Mirrors the SMS commands (CHECKIN <name> /
    CHECKOUT <name>) but uses the booking_id directly instead of
    fuzzy name resolution.
    """
    at: datetime | None = None


def _evict_admin_cache(tenant_id: uuid.UUID) -> None:
    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(tenant_id)
    except ImportError:
        pass


@router.post("/{booking_id}/checkin", response_model=BookingResponse)
async def admin_checkin_booking(
    booking_id: uuid.UUID,
    body: CheckInOverrideRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Admin manually checks a volunteer in via the booking detail UI.

    Source recorded as `admin_override`. Emits agent_call_log entry
    per decision #31. Evicts the live-events admin LLM cache.
    """
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.tenant_id == tenant.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    when = body.at or datetime.now(timezone.utc)
    prior = booking.checked_in_at
    booking.checked_in_at = when
    booking.checked_in_by_id = current_user.id
    booking.checked_in_source = CHECKIN_SOURCE_ADMIN_OVERRIDE

    db.add(
        AgentCallLog(
            tenant_id=tenant.id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_ADMIN_OVERRIDE,
            source="admin_ui",
            destination="admin_ui",
            decision_reason="manual_checkin",
            payload={
                "target_table": "bookings",
                "target_id": str(booking.id),
                "field": "checked_in_at",
                "prior_value": str(prior) if prior else None,
                "new_value": when.isoformat(),
                "admin_user_id": str(current_user.id),
            },
        )
    )
    _evict_admin_cache(tenant.id)
    await db.flush()
    await db.refresh(booking)
    return booking


@router.post("/{booking_id}/checkout", response_model=BookingResponse)
async def admin_checkout_booking(
    booking_id: uuid.UUID,
    body: CheckInOverrideRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Admin manually checks a volunteer out via the booking detail UI."""
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.tenant_id == tenant.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    when = body.at or datetime.now(timezone.utc)
    prior = booking.checked_out_at
    booking.checked_out_at = when
    booking.checked_out_by_id = current_user.id
    booking.checked_out_source = CHECKOUT_SOURCE_ADMIN_OVERRIDE

    db.add(
        AgentCallLog(
            tenant_id=tenant.id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_ADMIN_OVERRIDE,
            source="admin_ui",
            destination="admin_ui",
            decision_reason="manual_checkout",
            payload={
                "target_table": "bookings",
                "target_id": str(booking.id),
                "field": "checked_out_at",
                "prior_value": str(prior) if prior else None,
                "new_value": when.isoformat(),
                "admin_user_id": str(current_user.id),
            },
        )
    )
    _evict_admin_cache(tenant.id)
    await db.flush()
    await db.refresh(booking)
    return booking


class RunSheetVolunteer(BaseModel):
    booking_id: uuid.UUID
    contact_id: uuid.UUID
    name: str | None
    phone: str
    service_name: str | None
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    checked_in_source: str | None
    late_minutes: int | None


class RunSheetResponse(BaseModel):
    slot_id: uuid.UUID
    event_name: str
    location: str | None
    start_time: str
    end_time: str
    total_count: int
    checked_in_count: int
    volunteers: list[RunSheetVolunteer]


@router.get("/run-sheet/{slot_id}", response_model=RunSheetResponse)
async def get_run_sheet(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Run-sheet view for one event slot. Lists all non-cancelled bookings
    with their check-in state, late-flag, and current service.

    Polled by the run-sheet page every 30s.
    """
    slot_result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id,
            SpecificDateSlot.tenant_id == tenant.id,
        )
    )
    slot = slot_result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    bookings_result = await db.execute(
        select(Booking, Contact, AppointmentType)
        .join(Contact, Booking.contact_id == Contact.id)
        .join(AppointmentType, Booking.appointment_type_id == AppointmentType.id)
        .where(
            Booking.event_slot_id == slot_id,
            Booking.status != BookingStatus.CANCELLED,
        )
        .order_by(Contact.name)
    )

    # Late-checkin threshold reads tenant SystemSetting
    # `late_checkin_grace_minutes` (default 5 min). Phase 1 uses
    # the default; tenant overrides via the Settings page when
    # the Settings widget for this lands.
    late_grace_minutes = 5

    tz = pytz.timezone(tenant.business_timezone or "America/New_York")
    slot_start_local = tz.localize(
        datetime.combine(slot.date, slot.start_time)
    )
    slot_start_utc = slot_start_local.astimezone(timezone.utc)

    volunteers: list[RunSheetVolunteer] = []
    checked_in_count = 0
    for booking, contact, appt_type in bookings_result.all():
        late_min: int | None = None
        if booking.checked_in_at:
            checked_in_count += 1
            delta = (booking.checked_in_at - slot_start_utc).total_seconds() / 60
            if delta > late_grace_minutes:
                late_min = int(delta)
        volunteers.append(
            RunSheetVolunteer(
                booking_id=booking.id,
                contact_id=contact.id,
                name=contact.name,
                phone=contact.phone,
                service_name=appt_type.name,
                checked_in_at=booking.checked_in_at,
                checked_out_at=booking.checked_out_at,
                checked_in_source=booking.checked_in_source,
                late_minutes=late_min,
            )
        )

    return RunSheetResponse(
        slot_id=slot.id,
        event_name=slot.label or "(unnamed event)",
        location=slot.location,
        start_time=slot.start_time.strftime("%I:%M %p").lstrip("0"),
        end_time=slot.end_time.strftime("%I:%M %p").lstrip("0"),
        total_count=len(volunteers),
        checked_in_count=checked_in_count,
        volunteers=volunteers,
    )
