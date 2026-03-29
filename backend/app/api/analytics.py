from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import extract, func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.booking import Booking, BookingStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.pattern import CustomerAppointmentPattern, PatternConfidence
from app.models.reminder import Reminder, ReminderStatus
from app.schemas.analytics import (
    BookingVolumePoint,
    ConsentFunnel,
    ReminderAnalytics,
    RetentionMetrics,
    RevenuePoint,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/bookings", response_model=list[BookingVolumePoint])
async def get_booking_analytics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    months: int = Query(6, ge=1, le=24),
):
    """Booking volume by month."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    result = await db.execute(
        select(
            func.to_char(Booking.created_at, "YYYY-MM").label("period"),
            func.count().label("count"),
        )
        .where(Booking.tenant_id == tenant.id, Booking.created_at >= cutoff)
        .group_by("period")
        .order_by("period")
    )

    return [
        BookingVolumePoint(period=row.period, count=row.count)
        for row in result.all()
    ]


@router.get("/revenue", response_model=list[RevenuePoint])
async def get_revenue_analytics(
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    months: int = Query(6, ge=1, le=24),
):
    """Revenue by month."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    result = await db.execute(
        select(
            func.to_char(Booking.created_at, "YYYY-MM").label("period"),
            func.coalesce(func.sum(Booking.price_at_booking), 0).label("revenue"),
        )
        .where(
            Booking.tenant_id == tenant.id,
            Booking.created_at >= cutoff,
            Booking.status != BookingStatus.CANCELLED,
        )
        .group_by("period")
        .order_by("period")
    )

    return [
        RevenuePoint(period=row.period, revenue=float(row.revenue))
        for row in result.all()
    ]


@router.get("/retention", response_model=RetentionMetrics)
async def get_retention_analytics(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    total_patterns = (await db.execute(
        select(func.count()).where(CustomerAppointmentPattern.tenant_id == tenant.id)
    )).scalar() or 0

    personal_patterns = (await db.execute(
        select(func.count()).where(
            CustomerAppointmentPattern.tenant_id == tenant.id,
            CustomerAppointmentPattern.confidence == PatternConfidence.PERSONAL,
        )
    )).scalar() or 0

    recurring_rate = (personal_patterns / total_patterns * 100) if total_patterns > 0 else 0

    return RetentionMetrics(
        recurring_customer_rate=round(recurring_rate, 1),
        average_interval_accuracy=0.0,  # Calculated when pattern module is implemented
        total_recurring_customers=personal_patterns,
    )


@router.get("/reminders", response_model=ReminderAnalytics)
async def get_reminder_analytics(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    total_sent = (await db.execute(
        select(func.count()).where(
            Reminder.tenant_id == tenant.id,
            Reminder.status.in_([
                ReminderStatus.SENT, ReminderStatus.BOOKED,
                ReminderStatus.SKIPPED, ReminderStatus.NO_RESPONSE,
            ]),
        )
    )).scalar() or 0

    total_converted = (await db.execute(
        select(func.count()).where(
            Reminder.tenant_id == tenant.id,
            Reminder.status == ReminderStatus.BOOKED,
        )
    )).scalar() or 0

    conversion_rate = (total_converted / total_sent * 100) if total_sent > 0 else 0

    return ReminderAnalytics(
        total_sent=total_sent,
        total_converted=total_converted,
        conversion_rate=round(conversion_rate, 1),
        personal_conversion_rate=0.0,
        default_conversion_rate=0.0,
    )


@router.get("/consent", response_model=ConsentFunnel)
async def get_consent_analytics(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    total = (await db.execute(
        select(func.count()).where(ContactConsent.tenant_id == tenant.id)
    )).scalar() or 0

    statuses = {}
    for s in ConsentStatus:
        count = (await db.execute(
            select(func.count()).where(
                ContactConsent.tenant_id == tenant.id,
                ContactConsent.status == s,
            )
        )).scalar() or 0
        statuses[s.value] = count

    opt_in_rate = (statuses.get("opted_in", 0) / total * 100) if total > 0 else 0

    return ConsentFunnel(
        total_contacts=total,
        uncontacted=statuses.get("uncontacted", 0),
        pending=statuses.get("pending", 0),
        opted_in=statuses.get("opted_in", 0),
        opted_out=statuses.get("opted_out", 0),
        opt_in_rate=round(opt_in_rate, 1),
    )
