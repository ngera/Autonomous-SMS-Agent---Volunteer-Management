import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.notification import AdminNotification
from app.models.reminder import Reminder, ReminderStatus
from app.models.suspension import ContactSuspension
from app.schemas.dashboard import DashboardSummary, NotificationResponse, TodaysBooking

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    today = date.today()
    today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    today_end = datetime.combine(today, time.max, tzinfo=timezone.utc)

    # Today's bookings
    todays_bookings = (await db.execute(
        select(func.count()).where(
            Booking.tenant_id == tenant.id,
            Booking.scheduled_at.between(today_start, today_end),
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )).scalar() or 0

    # Pending conversations
    pending_convos = (await db.execute(
        select(func.count()).where(
            Conversation.tenant_id == tenant.id,
            Conversation.status == ConversationStatus.ACTIVE,
        )
    )).scalar() or 0

    # Reminders today
    reminders_today = (await db.execute(
        select(func.count()).where(
            Reminder.tenant_id == tenant.id,
            Reminder.scheduled_for == today,
            Reminder.status == ReminderStatus.PENDING,
        )
    )).scalar() or 0

    # Unreviewed suspensions
    unreviewed = (await db.execute(
        select(func.count()).where(
            ContactSuspension.tenant_id == tenant.id,
            ContactSuspension.reviewed_at.is_(None),
        )
    )).scalar() or 0

    # Monthly KPIs (current month)
    first_of_month = today.replace(day=1)
    month_start = datetime.combine(first_of_month, time.min, tzinfo=timezone.utc)

    monthly_bookings = (await db.execute(
        select(func.count()).where(
            Booking.tenant_id == tenant.id,
            Booking.created_at >= month_start,
            Booking.status != BookingStatus.CANCELLED,
        )
    )).scalar() or 0

    monthly_revenue = (await db.execute(
        select(func.coalesce(func.sum(Booking.price_at_booking), 0)).where(
            Booking.tenant_id == tenant.id,
            Booking.created_at >= month_start,
            Booking.status != BookingStatus.CANCELLED,
        )
    )).scalar() or 0

    # Opt-in rate
    total_contacts = (await db.execute(
        select(func.count()).where(ContactConsent.tenant_id == tenant.id)
    )).scalar() or 0
    opted_in = (await db.execute(
        select(func.count()).where(
            ContactConsent.tenant_id == tenant.id,
            ContactConsent.status == ConsentStatus.OPTED_IN,
        )
    )).scalar() or 0
    opt_in_rate = (opted_in / total_contacts * 100) if total_contacts > 0 else 0

    # Reminder conversion rate
    total_reminders_sent = (await db.execute(
        select(func.count()).where(
            Reminder.tenant_id == tenant.id,
            Reminder.status != ReminderStatus.PENDING,
        )
    )).scalar() or 0
    total_converted = (await db.execute(
        select(func.count()).where(
            Reminder.tenant_id == tenant.id,
            Reminder.status == ReminderStatus.BOOKED,
        )
    )).scalar() or 0
    conversion_rate = (total_converted / total_reminders_sent * 100) if total_reminders_sent > 0 else 0

    return DashboardSummary(
        todays_bookings_count=todays_bookings,
        pending_conversations_count=pending_convos,
        reminders_today_count=reminders_today,
        unreviewed_suspensions_count=unreviewed,
        monthly_bookings=monthly_bookings,
        monthly_revenue=float(monthly_revenue),
        opt_in_rate=round(opt_in_rate, 1),
        reminder_conversion_rate=round(conversion_rate, 1),
    )


@router.get("/todays-bookings", response_model=list[TodaysBooking])
async def get_todays_bookings(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    today = date.today()
    today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    today_end = datetime.combine(today, time.max, tzinfo=timezone.utc)

    from app.models.appointment_type import AppointmentType

    result = await db.execute(
        select(Booking, Contact.name, AppointmentType.name)
        .join(Contact, Booking.contact_phone == Contact.phone, isouter=True)
        .join(AppointmentType, Booking.appointment_type_id == AppointmentType.id, isouter=True)
        .where(
            Booking.tenant_id == tenant.id,
            Booking.scheduled_at.between(today_start, today_end),
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
        .order_by(Booking.scheduled_at)
    )

    bookings = []
    for row in result.all():
        booking, contact_name, appt_name = row
        bookings.append(TodaysBooking(
            id=booking.id,
            contact_phone=booking.contact_phone,
            contact_name=contact_name,
            appointment_type_name=appt_name or "Unknown",
            scheduled_at=booking.scheduled_at,
            status=booking.status.value,
        ))
    return bookings


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(AdminNotification)
        .where(AdminNotification.tenant_id == tenant.id)
        .where(
            (AdminNotification.admin_user_id == current_user.id)
            | (AdminNotification.admin_user_id.is_(None))
        )
        .where(AdminNotification.read_at.is_(None))
        .order_by(AdminNotification.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(AdminNotification).where(
            AdminNotification.id == notification_id,
            AdminNotification.tenant_id == tenant.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Notification marked as read"}
