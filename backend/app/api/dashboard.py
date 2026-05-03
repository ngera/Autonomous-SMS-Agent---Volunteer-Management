import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.announcement import Announcement, AnnouncementStatus
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule, SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.contact_preferred_type import ContactPreferredType
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.notification import AdminNotification
from app.models.system_setting import SystemSetting
from app.models.suspension import ContactSuspension
from app.schemas.dashboard import DashboardSummary, NotificationResponse, WeeklySlotStatus
from app.services.availability import _get_service_limits
from app.services.sms import send_sms

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def _compute_weekly_slot_statuses(db, tenant, day_offset_start: int = 0) -> list[dict]:
    """Compute booking status for availability windows over 7 days starting from offset."""
    import pytz
    tz = pytz.timezone(tenant.business_timezone)
    today = date.today()

    # Load appointment types
    appt_result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.tenant_id == tenant.id,
            AppointmentType.is_active.is_(True),
        )
    )
    appt_types = {str(a.id): a for a in appt_result.scalars().all()}

    # Load last reminder timestamps from system_settings
    reminder_keys_result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key.like("last_reminder_%"),
        )
    )
    reminder_timestamps = {}
    for s in reminder_keys_result.scalars().all():
        reminder_timestamps[s.key] = s.value

    # Build per-appointment-type map of latest SENT announcement timestamp.
    # Announcement applies to a service when filter_appointment_type_ids is empty
    # (broadcast) or explicitly includes that service's id.
    ann_rows = (await db.execute(
        select(Announcement.sent_at, Announcement.filter_appointment_type_ids).where(
            Announcement.tenant_id == tenant.id,
            Announcement.status == AnnouncementStatus.SENT,
            Announcement.sent_at.is_not(None),
        )
    )).all()
    last_announcement_map: dict[str, datetime] = {}
    for sent_at, filter_ids in ann_rows:
        target_ids = [str(x) for x in (filter_ids or [])] or list(appt_types.keys())
        for tid in target_ids:
            if tid not in appt_types:
                continue
            existing = last_announcement_map.get(tid)
            if existing is None or sent_at > existing:
                last_announcement_map[tid] = sent_at

    statuses = []
    for day_offset in range(day_offset_start, day_offset_start + 7):
        target_date = today + timedelta(days=day_offset)
        day_of_week = target_date.weekday()
        day_name = DAYS[day_of_week]

        windows = []
        rules_result = await db.execute(
            select(AvailabilityRule).where(
                AvailabilityRule.tenant_id == tenant.id,
                AvailabilityRule.day_of_week == day_of_week,
                AvailabilityRule.is_active.is_(True),
            )
        )
        for r in rules_result.scalars().all():
            windows.append((r.label, r.start_time, r.end_time, r.service_config, "recurring", r.location))

        specific_result = await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == tenant.id,
                SpecificDateSlot.date == target_date,
                SpecificDateSlot.is_active.is_(True),
            )
        )
        for s in specific_result.scalars().all():
            windows.append((s.label, s.start_time, s.end_time, s.service_config, "one_time", s.location))

        for label, start_t, end_t, svc_config, source, location in windows:
            window_time = f"{str(start_t)[:5]} – {str(end_t)[:5]}"

            if svc_config:
                services = svc_config
            else:
                services = [
                    {"appointment_type_id": aid, "min_required": 1, "max_allowed": 1}
                    for aid in appt_types
                ]

            window_start_dt = tz.localize(datetime.combine(target_date, start_t))
            window_end_dt = tz.localize(datetime.combine(target_date, end_t))

            for svc in services:
                appt_id = str(svc.get("appointment_type_id", ""))
                appt = appt_types.get(appt_id)
                if not appt:
                    continue

                min_req = svc.get("min_required", 1)
                max_allow = svc.get("max_allowed", 1)

                booked_result = await db.execute(
                    select(func.count()).where(
                        Booking.tenant_id == tenant.id,
                        Booking.appointment_type_id == uuid.UUID(appt_id),
                        Booking.scheduled_at >= window_start_dt,
                        Booking.scheduled_at < window_end_dt,
                        Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
                    )
                )
                booked = booked_result.scalar() or 0

                if booked >= max_allow:
                    slot_status = "full"
                elif booked >= min_req:
                    slot_status = "met_minimum"
                else:
                    slot_status = "needs_more"

                # Lookup last reminder sent
                reminder_key = f"last_reminder_{target_date}_{appt_id}"
                last_sent_str = reminder_timestamps.get(reminder_key)
                last_sent = None
                if last_sent_str:
                    try:
                        last_sent = datetime.fromisoformat(last_sent_str)
                    except ValueError:
                        pass

                statuses.append({
                    "date": str(target_date),
                    "day_name": day_name,
                    "window_label": label,
                    "window_time": window_time,
                    "service_name": appt.name,
                    "appointment_type_id": appt_id,
                    "min_required": min_req,
                    "max_allowed": max_allow,
                    "booked": booked,
                    "status": slot_status,
                    "source": source,
                    "location": location,
                    "last_reminder_sent": last_sent,
                    "last_announcement_sent": last_announcement_map.get(appt_id),
                })

    return statuses


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    today = date.today()
    today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    today_end = datetime.combine(today, time.max, tzinfo=timezone.utc)

    todays_bookings = (await db.execute(
        select(func.count()).where(
            Booking.tenant_id == tenant.id,
            Booking.scheduled_at.between(today_start, today_end),
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )).scalar() or 0

    unreviewed = (await db.execute(
        select(func.count()).where(
            ContactSuspension.tenant_id == tenant.id,
            ContactSuspension.reviewed_at.is_(None),
        )
    )).scalar() or 0

    first_of_month = today.replace(day=1)
    month_start = datetime.combine(first_of_month, time.min, tzinfo=timezone.utc)
    monthly_bookings = (await db.execute(
        select(func.count()).where(
            Booking.tenant_id == tenant.id,
            Booking.created_at >= month_start,
            Booking.status != BookingStatus.CANCELLED,
        )
    )).scalar() or 0

    weekly_statuses = await _compute_weekly_slot_statuses(db, tenant)
    slots_needing = sum(1 for s in weekly_statuses if s["status"] == "needs_more")

    # Total active volunteers
    total_volunteers = (await db.execute(
        select(func.count()).where(
            Contact.tenant_id == tenant.id,
            Contact.status == "active",
        )
    )).scalar() or 0

    suspended_or_banned = (await db.execute(
        select(func.count()).where(
            Contact.tenant_id == tenant.id,
            Contact.status.in_(["suspended", "banned"]),
        )
    )).scalar() or 0

    # Volunteers by service — count preferred type links
    appt_types_result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.tenant_id == tenant.id,
            AppointmentType.is_active.is_(True),
        )
    )
    appt_types = appt_types_result.scalars().all()

    # Count contacts with any preference set
    contacts_with_prefs = (await db.execute(
        select(func.count(func.distinct(ContactPreferredType.contact_id))).where(
            ContactPreferredType.tenant_id == tenant.id,
        )
    )).scalar() or 0
    # Contacts with no prefs = participate in everything
    no_pref_count = total_volunteers - contacts_with_prefs

    # Compute occurrences and min_per_slot per service over next 30 days
    # For each service: count how many time slots it appears in across weekly rules + specific dates
    all_rules_result = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.is_active.is_(True),
        )
    )
    all_rules = all_rules_result.scalars().all()

    end_date = today + timedelta(days=30)
    all_specific_result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date >= today,
            SpecificDateSlot.date <= end_date,
        )
    )
    all_specific = all_specific_result.scalars().all()

    # Per service: track min_per_slot, max_per_slot, occurrences in 30 days
    service_demand: dict[str, dict] = {}

    day_counts: dict[int, int] = {}
    for day_off in range(30):
        dow = (today + timedelta(days=day_off)).weekday()
        day_counts[dow] = day_counts.get(dow, 0) + 1

    for rule in all_rules:
        occ = day_counts.get(rule.day_of_week, 0)
        if rule.service_config:
            for cfg in rule.service_config:
                aid = str(cfg.get("appointment_type_id", ""))
                if aid not in service_demand:
                    service_demand[aid] = {"occurrences": 0, "min": 0, "max": 0}
                service_demand[aid]["occurrences"] += occ
                service_demand[aid]["min"] = max(service_demand[aid]["min"], cfg.get("min_required", 1))
                service_demand[aid]["max"] = max(service_demand[aid]["max"], cfg.get("max_allowed", 1))
        else:
            for at in appt_types:
                aid = str(at.id)
                if aid not in service_demand:
                    service_demand[aid] = {"occurrences": 0, "min": 0, "max": 0}
                service_demand[aid]["occurrences"] += occ
                service_demand[aid]["min"] = max(service_demand[aid]["min"], 1)
                service_demand[aid]["max"] = max(service_demand[aid]["max"], 1)

    for sds in all_specific:
        if sds.service_config:
            for cfg in sds.service_config:
                aid = str(cfg.get("appointment_type_id", ""))
                if aid not in service_demand:
                    service_demand[aid] = {"occurrences": 0, "min": 0, "max": 0}
                service_demand[aid]["occurrences"] += 1
                service_demand[aid]["min"] = max(service_demand[aid]["min"], cfg.get("min_required", 1))
                service_demand[aid]["max"] = max(service_demand[aid]["max"], cfg.get("max_allowed", 1))
        else:
            for at in appt_types:
                aid = str(at.id)
                if aid not in service_demand:
                    service_demand[aid] = {"occurrences": 0, "min": 0, "max": 0}
                service_demand[aid]["occurrences"] += 1
                service_demand[aid]["min"] = max(service_demand[aid]["min"], 1)
                service_demand[aid]["max"] = max(service_demand[aid]["max"], 1)

    volunteers_by_service = []
    for at in appt_types:
        aid = str(at.id)
        specific_count = (await db.execute(
            select(func.count()).where(
                ContactPreferredType.tenant_id == tenant.id,
                ContactPreferredType.appointment_type_id == at.id,
            )
        )).scalar() or 0
        available = specific_count + no_pref_count
        demand = service_demand.get(aid, {"occurrences": 0, "min": 1, "max": 1})
        min_per = demand["min"] or 1
        max_per = demand["max"] or 1
        occurrences = demand["occurrences"]
        buffer = available - min_per
        buffer_pct = round((buffer / min_per) * 100, 0) if min_per > 0 else 0

        volunteers_by_service.append({
            "service_name": at.name,
            "available": available,
            "min_per_slot": min_per,
            "max_per_slot": max_per,
            "occurrences_30d": occurrences,
            "buffer": buffer,
            "buffer_pct": buffer_pct,
        })

    return DashboardSummary(
        todays_bookings_count=todays_bookings,
        unreviewed_suspensions_count=unreviewed,
        suspended_or_banned_count=suspended_or_banned,
        monthly_bookings=monthly_bookings,
        slots_needing_bookings=slots_needing,
        total_volunteers=total_volunteers,
        volunteers_by_service=volunteers_by_service,
    )


@router.get("/weekly-slots", response_model=list[WeeklySlotStatus])
async def get_weekly_slot_statuses(
    db: DbSession, current_user: CurrentUser, tenant: CurrentTenant,
    offset: int = 0,
):
    """Get weekly slot statuses. offset=0 means next 7 days, offset=7 means days 8-14, etc."""
    return await _compute_weekly_slot_statuses(db, tenant, day_offset_start=offset)


class SendReminderRequest(BaseModel):
    date: str  # YYYY-MM-DD
    appointment_type_id: str


@router.post("/send-reminder")
async def send_slot_reminder(
    body: SendReminderRequest, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    """Send reminders for a specific service on a specific date.

    - Volunteers who participate in this service but haven't booked get a "please sign up" message.
    - Volunteers who have already booked get a confirmation reminder.
    """
    import pytz
    tz = pytz.timezone(tenant.business_timezone)
    target_date = date.fromisoformat(body.date)
    appt_uuid = uuid.UUID(body.appointment_type_id)

    # Load appointment type
    appt_result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == appt_uuid)
    )
    appt_type = appt_result.scalar_one_or_none()
    if not appt_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    day_start = tz.localize(datetime.combine(target_date, time.min))
    day_end = tz.localize(datetime.combine(target_date, time.max))

    # Get volunteers who participate in this service
    pref_result = await db.execute(
        select(Contact).join(
            ContactPreferredType, ContactPreferredType.contact_id == Contact.id
        ).where(
            ContactPreferredType.tenant_id == tenant.id,
            ContactPreferredType.appointment_type_id == appt_uuid,
            Contact.status == "active",
        )
    )
    participating_volunteers = pref_result.scalars().all()

    # Also include volunteers with no preferences (they participate in everything)
    all_contacts_result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant.id, Contact.status == "active")
    )
    all_contacts = all_contacts_result.scalars().all()
    contacts_with_prefs = {c.id for c in participating_volunteers}
    contacts_with_any_pref = set()
    any_pref_result = await db.execute(
        select(ContactPreferredType.contact_id).where(
            ContactPreferredType.tenant_id == tenant.id,
        ).distinct()
    )
    contacts_with_any_pref = {row[0] for row in any_pref_result.all()}

    # Volunteers with no prefs at all = participate in everything
    no_pref_volunteers = [c for c in all_contacts if c.id not in contacts_with_any_pref]
    target_volunteers = list(participating_volunteers) + no_pref_volunteers

    if not target_volunteers:
        return {"sent_signup": 0, "sent_confirmation": 0, "message": "No participating volunteers found."}

    # Get who has already booked this service on this date
    booked_result = await db.execute(
        select(Booking.contact_id).where(
            Booking.tenant_id == tenant.id,
            Booking.appointment_type_id == appt_uuid,
            Booking.scheduled_at >= day_start,
            Booking.scheduled_at < day_end,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )
    booked_contact_ids = {row[0] for row in booked_result.all()}

    date_str = target_date.strftime("%A %B %d")
    sent_signup = 0
    sent_confirmation = 0

    for volunteer in target_volunteers:
        if volunteer.id in booked_contact_ids:
            # Confirmation reminder
            msg = f"Reminder: You are signed up for {appt_type.name} on {date_str}. Thank you!"
            try:
                await send_sms(to=volunteer.phone, body=msg, tenant=tenant)
                sent_confirmation += 1
            except Exception:
                pass
        else:
            # Signup reminder
            msg = f"We still need volunteers for {appt_type.name} on {date_str}. Reply to sign up for a time slot!"
            try:
                await send_sms(to=volunteer.phone, body=msg, tenant=tenant)
                sent_signup += 1
            except Exception:
                pass

    # Record last reminder timestamp
    reminder_key = f"last_reminder_{target_date}_{body.appointment_type_id}"
    existing = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key == reminder_key,
        )
    )
    setting = existing.scalar_one_or_none()
    now_str = datetime.now(timezone.utc).isoformat()
    if setting:
        setting.value = now_str
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSetting(
            tenant_id=tenant.id,
            key=reminder_key,
            value=now_str,
        ))
    await db.flush()

    return {
        "sent_signup": sent_signup,
        "sent_confirmation": sent_confirmation,
        "total_volunteers": len(target_volunteers),
    }


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
