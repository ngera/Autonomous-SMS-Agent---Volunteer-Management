import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DbSession, ManagerUser
from app.models.reminder import Reminder, ReminderStatus
from app.schemas.reminder import (
    ReminderCancelRequest,
    ReminderListResponse,
    ReminderResponse,
    ReminderTriggerRequest,
    ReminderUpdate,
)

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@router.get("/upcoming", response_model=ReminderListResponse)
async def get_upcoming_reminders(db: DbSession, current_user: CurrentUser):
    today = date.today()
    query = select(Reminder).where(
        Reminder.scheduled_for >= today,
        Reminder.status == ReminderStatus.PENDING,
    ).order_by(Reminder.scheduled_for)

    result = await db.execute(query)
    items = result.scalars().all()
    return ReminderListResponse(items=items, total=len(items))


@router.get("/history", response_model=ReminderListResponse)
async def get_reminder_history(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Reminder).where(
        Reminder.status != ReminderStatus.PENDING,
    ).order_by(Reminder.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)

    return ReminderListResponse(items=result.scalars().all(), total=total)


@router.post("/trigger", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def trigger_reminder(
    body: ReminderTriggerRequest, db: DbSession, current_user: ManagerUser
):
    """Manually trigger a reminder for a specific customer."""
    reminder = Reminder(
        contact_phone=body.contact_phone,
        appointment_type_id=body.appointment_type_id,
        scheduled_for=date.today(),
        status=ReminderStatus.PENDING,
    )
    db.add(reminder)
    await db.flush()

    # TODO: Send actual reminder SMS in Phase 5
    reminder.status = ReminderStatus.SENT
    reminder.sent_at = datetime.now(timezone.utc)
    await db.flush()

    await db.refresh(reminder)
    return reminder


@router.put("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: uuid.UUID,
    body: ReminderUpdate,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(
        select(Reminder).where(Reminder.id == reminder_id)
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.status != ReminderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only edit pending reminders")

    reminder.scheduled_for = body.scheduled_for
    await db.flush()
    await db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reminder(
    reminder_id: uuid.UUID,
    body: ReminderCancelRequest,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(
        select(Reminder).where(Reminder.id == reminder_id)
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.status != ReminderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only cancel pending reminders")

    reminder.status = ReminderStatus.CANCELLED
    reminder.skip_reason = body.reason
    await db.flush()


@router.get("/analytics")
async def get_reminder_analytics(db: DbSession, current_user: CurrentUser):
    """Reminder conversion analytics. Full implementation in Phase 7."""
    total_sent = (await db.execute(
        select(func.count()).where(Reminder.status != ReminderStatus.PENDING)
    )).scalar() or 0

    total_converted = (await db.execute(
        select(func.count()).where(Reminder.status == ReminderStatus.BOOKED)
    )).scalar() or 0

    conversion_rate = (total_converted / total_sent * 100) if total_sent > 0 else 0

    return {
        "total_sent": total_sent,
        "total_converted": total_converted,
        "conversion_rate": round(conversion_rate, 1),
        "personal_conversion_rate": 0.0,
        "default_conversion_rate": 0.0,
    }
