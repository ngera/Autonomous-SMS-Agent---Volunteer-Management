import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DbSession, ManagerUser
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking, BookingStatus
from app.models.booking_history import BookingEventType, BookingHistory, ChangedBy
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: BookingStatus | None = Query(None, alias="status"),
    appointment_type_id: uuid.UUID | None = None,
    contact_phone: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    query = select(Booking)

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

    return BookingListResponse(
        items=result.scalars().all(),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(body: BookingCreate, db: DbSession, current_user: ManagerUser):
    """Create a manual booking (bypasses chatbot)."""
    # Verify appointment type exists
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == body.appointment_type_id)
    )
    if not appt_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Appointment type not found")

    booking = Booking(
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
    await process_booking_creation(db, booking)

    await db.refresh(booking)
    return booking


@router.put("/{booking_id}/reschedule", response_model=BookingResponse)
async def reschedule_booking(
    booking_id: uuid.UUID,
    body: RescheduleRequest,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
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
    await process_booking_reschedule(db, booking)

    await db.refresh(booking)
    return booking


@router.put("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id: uuid.UUID,
    body: StatusUpdateRequest,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    old_status = booking.status
    booking.status = body.status

    if body.status == BookingStatus.COMPLETED:
        booking.completed_at = datetime.now(timezone.utc)

    history = BookingHistory(
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
        )

    await db.refresh(booking)
    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: uuid.UUID, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {booking.status.value} booking")

    old_status = booking.status
    booking.status = BookingStatus.CANCELLED
    booking.ics_sequence += 1

    history = BookingHistory(
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
    await process_booking_cancellation(db, booking)


@router.get("/{booking_id}/history", response_model=list[BookingHistoryResponse])
async def get_booking_history(
    booking_id: uuid.UUID, db: DbSession, current_user: CurrentUser
):
    result = await db.execute(
        select(BookingHistory)
        .where(BookingHistory.booking_id == booking_id)
        .order_by(BookingHistory.created_at)
    )
    return result.scalars().all()
