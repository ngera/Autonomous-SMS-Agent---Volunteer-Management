import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking, BookingStatus
from app.models.booking_history import BookingEventType, BookingHistory, ChangedBy
from app.models.contact import Contact
from app.schemas.booking import (
    BookingCreate,
    BookingHistoryResponse,
    BookingListResponse,
    BookingResponse,
    RescheduleRequest,
    StatusUpdateRequest,
)

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status_filter: BookingStatus | None = Query(None, alias="status"),
    appointment_type_id: uuid.UUID | None = None,
    contact_phone: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    query = select(Booking).where(Booking.tenant_id == tenant.id)

    if status_filter:
        query = query.where(Booking.status == status_filter)
    if appointment_type_id:
        query = query.where(Booking.appointment_type_id == appointment_type_id)
    if contact_phone:
        query = query.where(Booking.contact_phone == contact_phone)
    if date_from:
        query = query.where(Booking.scheduled_at >= date_from)
    if date_to:
        query = query.where(Booking.scheduled_at <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Booking.scheduled_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    bookings = result.scalars().all()

    # Enrich with contact names and appointment type info
    enriched = [await _enrich_booking(db, b) for b in bookings]

    return BookingListResponse(
        items=enriched,
        total=total,
        page=page,
        page_size=page_size,
    )


async def _enrich_booking(db, b: Booking) -> BookingResponse:
    contact_result = await db.execute(
        select(Contact.name).where(Contact.id == b.contact_id)
    )
    contact_name = contact_result.scalar_one_or_none()
    appt_result = await db.execute(
        select(AppointmentType.name, AppointmentType.duration_minutes).where(
            AppointmentType.id == b.appointment_type_id
        )
    )
    appt_row = appt_result.one_or_none()
    return BookingResponse(
        id=b.id,
        contact_phone=b.contact_phone,
        appointment_type_id=b.appointment_type_id,
        scheduled_at=b.scheduled_at,
        confirmed_at=b.confirmed_at,
        completed_at=b.completed_at,
        status=b.status,
        price_at_booking=b.price_at_booking,
        calendar_event_id=b.calendar_event_id,
        ics_sequence=b.ics_sequence,
        ics_new_url=b.ics_new_url,
        ics_update_url=b.ics_update_url,
        conversation_id=b.conversation_id,
        created_at=b.created_at,
        contact_name=contact_name,
        appointment_type_name=appt_row[0] if appt_row else None,
        duration_minutes=appt_row[1] if appt_row else None,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: uuid.UUID, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return await _enrich_booking(db, booking)


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    """Create a manual booking (bypasses chatbot)."""
    # Verify appointment type exists within tenant
    appt_result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == body.appointment_type_id,
            AppointmentType.tenant_id == tenant.id,
        )
    )
    if not appt_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Appointment type not found")

    # Resolve contact_id from phone within tenant
    contact_result = await db.execute(
        select(Contact).where(
            Contact.phone == body.contact_phone,
            Contact.tenant_id == tenant.id,
        )
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.background_check_required:
        raise HTTPException(
            status_code=400,
            detail="This volunteer has a pending background check requirement. Clear the flag on their profile before booking.",
        )

    booking = Booking(
        tenant_id=tenant.id,
        contact_id=contact.id,
        contact_phone=body.contact_phone,
        appointment_type_id=body.appointment_type_id,
        scheduled_at=body.scheduled_at,
        price_at_booking=body.price_at_booking,
        status=BookingStatus.SCHEDULED,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(booking)
    await db.flush()

    # Record history
    history = BookingHistory(
        tenant_id=tenant.id,
        booking_id=booking.id,
        event_type=BookingEventType.CREATED,
        new_status=BookingStatus.SCHEDULED,
        new_scheduled_at=body.scheduled_at,
        changed_by=ChangedBy.ADMIN,
        changed_by_admin_id=current_user.id,
        notes="Manual booking created via admin panel",
    )
    db.add(history)
    await db.flush()

    # Calendar event, ICS URLs, and SMS confirmation
    from app.services.booking import process_booking_creation
    await process_booking_creation(db, booking, tenant=tenant)

    await db.refresh(booking)
    return booking


@router.put("/{booking_id}/reschedule", response_model=BookingResponse)
async def reschedule_booking(
    booking_id: uuid.UUID,
    body: RescheduleRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED, BookingStatus.NO_SHOW):
        raise HTTPException(status_code=400, detail=f"Cannot reschedule a {booking.status.value} booking")

    old_scheduled_at = booking.scheduled_at
    old_status = booking.status

    booking.scheduled_at = body.new_scheduled_at
    booking.status = BookingStatus.RESCHEDULED
    booking.ics_sequence += 1

    history = BookingHistory(
        tenant_id=tenant.id,
        booking_id=booking.id,
        event_type=BookingEventType.RESCHEDULED,
        previous_scheduled_at=old_scheduled_at,
        new_scheduled_at=body.new_scheduled_at,
        previous_status=old_status,
        new_status=BookingStatus.RESCHEDULED,
        changed_by=ChangedBy.ADMIN,
        changed_by_admin_id=current_user.id,
    )
    db.add(history)
    await db.flush()

    # Update calendar event and send SMS + ICS
    from app.services.booking import process_booking_reschedule
    await process_booking_reschedule(db, booking, tenant=tenant)

    await db.refresh(booking)
    return booking


@router.put("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id: uuid.UUID,
    body: StatusUpdateRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    old_status = booking.status
    booking.status = body.status

    if body.status == BookingStatus.COMPLETED:
        booking.completed_at = datetime.now(timezone.utc)

    history = BookingHistory(
        tenant_id=tenant.id,
        booking_id=booking.id,
        event_type=BookingEventType.STATUS_CHANGED,
        previous_status=old_status,
        new_status=body.status,
        changed_by=ChangedBy.ADMIN,
        changed_by_admin_id=current_user.id,
        notes=body.notes,
    )
    db.add(history)
    await db.flush()

    # Recalculate recurrence pattern when booking is completed
    if body.status == BookingStatus.COMPLETED:
        from app.modules.pattern import recalculate_pattern
        await recalculate_pattern(
            db,
            booking.contact_phone,
            str(booking.appointment_type_id),
            tenant_id=tenant.id,
        )

    await db.refresh(booking)
    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: uuid.UUID, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {booking.status.value} booking")

    old_status = booking.status
    booking.status = BookingStatus.CANCELLED
    booking.ics_sequence += 1

    history = BookingHistory(
        tenant_id=tenant.id,
        booking_id=booking.id,
        event_type=BookingEventType.CANCELLED,
        previous_status=old_status,
        new_status=BookingStatus.CANCELLED,
        changed_by=ChangedBy.ADMIN,
        changed_by_admin_id=current_user.id,
    )
    db.add(history)
    await db.flush()

    # Delete calendar event and send SMS + ICS cancellation
    from app.services.booking import process_booking_cancellation
    await process_booking_cancellation(db, booking, tenant=tenant)


@router.get("/{booking_id}/history", response_model=list[BookingHistoryResponse])
async def get_booking_history(
    booking_id: uuid.UUID, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(BookingHistory)
        .where(
            BookingHistory.booking_id == booking_id,
            BookingHistory.tenant_id == tenant.id,
        )
        .order_by(BookingHistory.created_at)
    )
    return result.scalars().all()
