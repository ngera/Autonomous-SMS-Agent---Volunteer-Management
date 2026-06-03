import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
            Announcement.status == AnnouncementStatus.SENT.value,
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
            windows.append((r.label, r.start_time, r.end_time, r.service_config, "recurring", r.location, r.allow_roster_sharing, str(r.id)))

        specific_result = await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == tenant.id,
                SpecificDateSlot.date == target_date,
                SpecificDateSlot.is_active.is_(True),
            )
        )
        for s in specific_result.scalars().all():
            windows.append((s.label, s.start_time, s.end_time, s.service_config, "one_time", s.location, s.allow_roster_sharing, str(s.id)))

        for label, start_t, end_t, svc_config, source, location, allow_roster_sharing, source_id in windows:
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

                roster_rows = (await db.execute(
                    select(
                        Contact.name,
                        Contact.phone,
                        Booking.roster_visibility,
                    )
                    .join(Contact, Contact.id == Booking.contact_id)
                    .where(
                        Booking.tenant_id == tenant.id,
                        Booking.appointment_type_id == uuid.UUID(appt_id),
                        Booking.scheduled_at >= window_start_dt,
                        Booking.scheduled_at < window_end_dt,
                        Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
                    )
                )).all()
                booked = len(roster_rows)
                roster = [
                    {
                        "name": (cname or cphone),
                        "phone": cphone,
                        "visibility": (vis if isinstance(vis, str) else (vis.value if vis else "first_name")),
                    }
                    for (cname, cphone, vis) in roster_rows
                ]

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
                    "source_id": source_id,
                    "location": location,
                    "allow_roster_sharing": allow_roster_sharing,
                    "roster": roster,
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

    # Load the configurable signup-reminder template; fall back to default on bad placeholders
    from app.prompts.conversation import get_reminder_format_template
    template = await get_reminder_format_template(db, tenant.id)

    class _Defaulting(dict):
        def __missing__(self, key: str) -> str:
            return ""

    template_ctx = _Defaulting({
        "service_name": appt_type.name,
        "date": date_str,
    })
    try:
        signup_msg = template.format_map(template_ctx)
    except (ValueError, KeyError, IndexError):
        signup_msg = (
            f"We still need volunteers for {appt_type.name} on {date_str}. "
            "Reply to sign up for a time slot!"
        )

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
            # Signup reminder (admin-configurable template)
            msg = signup_msg
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


# ── Live Events panel (decision #21) ──────────────────────────────


class LiveEventRow(BaseModel):
    slot_id: uuid.UUID
    event_name: str
    location: str | None
    start_time: str
    end_time: str
    total_count: int
    checked_in_count: int
    missing_count: int
    first_missing_names: list[str]
    pending_switches: int  # Phase 3 — count of pending booking_service_log rows for this slot
    status_dot: str  # 'red' | 'amber' | 'green'


@router.get("/live-events", response_model=list[LiveEventRow])
async def list_live_events(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Lightweight aggregate over slots currently in the live window
    [start_at - 30min, end_at + 1h]. Polled every 30s by the dashboard
    Live Events panel and run-sheet pages.

    No PII beyond first-name list (capped at 3).
    """
    from app.models.booking_service_log import BSL_STATUS_PENDING, BookingServiceLog
    from app.services.event_eligibility import _slot_in_live_window

    today = date.today()
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(
                today - timedelta(days=1), today + timedelta(days=1)
            ),
        )
    )
    now_utc = datetime.now(timezone.utc)
    rows: list[LiveEventRow] = []
    for slot in result.scalars().all():
        if not _slot_in_live_window(slot, now_utc):
            continue
        bookings_result = await db.execute(
            select(Booking, Contact)
            .join(Contact, Booking.contact_id == Contact.id)
            .where(
                Booking.event_slot_id == slot.id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
        bookings_with_contacts = bookings_result.all()
        total = len(bookings_with_contacts)
        checked_in = sum(1 for b, _ in bookings_with_contacts if b.checked_in_at is not None)
        missing = total - checked_in
        first_missing = []
        for b, c in bookings_with_contacts:
            if b.checked_in_at is None and c.name:
                first_missing.append((c.name.split() or [""])[0])
            if len(first_missing) >= 3:
                break

        # Phase 3 — pending service-switch count for this slot.
        pending_q = await db.execute(
            select(func.count())
            .select_from(BookingServiceLog)
            .join(Booking, BookingServiceLog.booking_id == Booking.id)
            .where(
                BookingServiceLog.tenant_id == tenant.id,
                BookingServiceLog.status == BSL_STATUS_PENDING,
                Booking.event_slot_id == slot.id,
            )
        )
        pending_switches = int(pending_q.scalar() or 0)

        # Color-coded urgency: red = missing check-ins, amber = pending
        # service approvals waiting (and everyone's in), green = clean.
        if missing > 0:
            status_dot = "red"
        elif pending_switches > 0:
            status_dot = "amber"
        else:
            status_dot = "green"

        rows.append(LiveEventRow(
            slot_id=slot.id,
            event_name=slot.label or "(unnamed event)",
            location=slot.location,
            start_time=slot.start_time.strftime("%I:%M %p").lstrip("0"),
            end_time=slot.end_time.strftime("%I:%M %p").lstrip("0"),
            total_count=total,
            checked_in_count=checked_in,
            missing_count=missing,
            first_missing_names=first_missing,
            pending_switches=pending_switches,
            status_dot=status_dot,
        ))
    # Sort by urgency: missing > 0 first, then by start_at.
    rows.sort(key=lambda r: (r.missing_count == 0, r.start_time))
    return rows


# ─── Needs-You-Now alerts ────────────────────────────────────────
#
# Unified triage feed for the redesigned dashboard. Aggregates
# action-required items from every operational source so the admin
# sees one prioritized list instead of N panels to cross-reference.
#
# Sources today (Phase 1):
#   - pending booking_service_log (SWITCH / ALSO awaiting approval)
#   - pending booking_review rows (post-event grades)
#   - unreviewed contact_suspension rows (auto-suspends needing OWNER review)
#   - volunteer_candidate rows awaiting promote / dismiss
#   - at-risk events in the next 7 days (under-filled, no campaign)
#   - dummy issue-report items (complaints / hallucinations / feedback) —
#     wired as placeholders so the layout is final. Replaced with real
#     data once the issue-reporting backend ships.

class AlertItem(BaseModel):
    id: str
    source: str           # e.g. "service_switch", "review", "suspension"…
    severity: str         # "high" | "medium" | "low"
    title: str
    body: str | None = None
    cta_label: str
    cta_url: str          # frontend route
    age_seconds: int      # for "5m ago" rendering
    icon: str             # lucide icon name hint
    accent: str           # color accent: "amber" | "red" | "blue" | "violet" | "rose" | "slate"
    context: dict | None = None


# Severity → numeric sort key (lower fires first).
_SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def _age(now: datetime, then: datetime | None) -> int:
    if then is None:
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, int((now - then).total_seconds()))


async def _alerts_service_switches(db, tenant, now) -> list[AlertItem]:
    """Pending SWITCH / ALSO mid-event service changes."""
    from app.models.booking_service_log import (
        BSL_STATUS_PENDING,
        BookingServiceLog,
    )

    result = await db.execute(
        select(BookingServiceLog, Booking, Contact, SpecificDateSlot)
        .join(Booking, BookingServiceLog.booking_id == Booking.id)
        .join(Contact, Booking.contact_id == Contact.id)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .where(
            BookingServiceLog.tenant_id == tenant.id,
            BookingServiceLog.status == BSL_STATUS_PENDING,
        )
        .order_by(BookingServiceLog.created_at.asc())
        .limit(25)
    )
    items: list[AlertItem] = []
    for log_row, booking, contact, slot in result.all():
        first = (contact.name or contact.phone).split()[0] if contact.name else (contact.phone or "Volunteer")
        target = log_row.requested_service_name or "another service"
        items.append(AlertItem(
            id=f"switch:{log_row.id}",
            source="service_switch",
            severity="high",
            title=f"{first} wants to {log_row.change_kind or 'switch'} → {target}",
            body=f"At {slot.label or 'event'} · approve or reject in the run sheet.",
            cta_label="Open run sheet",
            cta_url=f"/run-sheet/{slot.id}",
            age_seconds=_age(now, log_row.created_at),
            icon="ArrowRightLeft",
            accent="amber",
            context={"slot_id": str(slot.id), "booking_id": str(booking.id)},
        ))
    return items


async def _alerts_pending_reviews(db, tenant, now) -> list[AlertItem]:
    from app.models.booking_review import REVIEW_STATUS_PENDING, BookingReview

    result = await db.execute(
        select(BookingReview, Booking, SpecificDateSlot)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .where(
            BookingReview.tenant_id == tenant.id,
            BookingReview.status == REVIEW_STATUS_PENDING,
        )
        .order_by(BookingReview.created_at.asc())
        .limit(25)
    )
    rows = result.all()
    # Group by slot_id to collapse "5 reviews on Saturday gala" into one row.
    by_slot: dict[uuid.UUID, list] = {}
    for review, booking, slot in rows:
        by_slot.setdefault(slot.id, []).append((review, booking, slot))

    items: list[AlertItem] = []
    for slot_id, group in by_slot.items():
        first_review, _, slot = group[0]
        n = len(group)
        items.append(AlertItem(
            id=f"reviews:{slot_id}",
            source="review",
            severity="medium",
            title=(
                f"{n} review to grade"
                if n == 1
                else f"{n} reviews to grade"
            ),
            body=f"{slot.label or 'event'} on {slot.date.strftime('%a, %b %-d') if hasattr(slot.date, 'strftime') else slot.date}.",
            cta_label="Grade reviews",
            cta_url=f"/event-review/{slot_id}",
            age_seconds=_age(now, first_review.created_at),
            icon="ClipboardCheck",
            accent="violet",
            context={"slot_id": str(slot_id), "count": n},
        ))
    return items


async def _alerts_unreviewed_suspensions(db, tenant, now) -> list[AlertItem]:
    result = await db.execute(
        select(ContactSuspension, Contact)
        .join(Contact, ContactSuspension.contact_id == Contact.id)
        .where(
            ContactSuspension.tenant_id == tenant.id,
            ContactSuspension.reviewed_at.is_(None),
        )
        .order_by(ContactSuspension.suspended_at.asc())
        .limit(15)
    )
    items: list[AlertItem] = []
    for sus, contact in result.all():
        items.append(AlertItem(
            id=f"suspension:{sus.id}",
            source="suspension",
            severity="medium",
            title=f"Suspension to review: {contact.name or contact.phone}",
            body=(sus.reason or "Auto-suspended — needs OWNER review."),
            cta_label="Review",
            cta_url="/suspensions",
            age_seconds=_age(now, sus.suspended_at),
            icon="ShieldAlert",
            accent="rose",
            context={"contact_id": str(contact.id)},
        ))
    return items


async def _alerts_walkup_candidates(db, tenant, now) -> list[AlertItem]:
    from app.models.volunteer_candidate import VolunteerCandidate

    result = await db.execute(
        select(VolunteerCandidate)
        .where(
            VolunteerCandidate.tenant_id == tenant.id,
            VolunteerCandidate.decisioned_at.is_(None),
        )
        .order_by(VolunteerCandidate.created_at.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    if not rows:
        return []
    return [AlertItem(
        id=f"candidates:summary",
        source="candidate",
        severity="medium",
        title=(
            f"{len(rows)} walk-up candidate awaiting decision"
            if len(rows) == 1
            else f"{len(rows)} walk-up candidates awaiting decision"
        ),
        body="Unknown phones that texted HERE. Promote or dismiss.",
        cta_label="Triage candidates",
        cta_url="/candidates",
        age_seconds=_age(now, rows[0].created_at),
        icon="UserPlus",
        accent="blue",
        context={"count": len(rows)},
    )]


async def _alerts_at_risk_events(db, tenant, now) -> list[AlertItem]:
    """Events in the next 7 days that are under-filled at < 60% with no
    pending campaign. These get auto-promoted from passive list items to
    actionable alerts."""
    today = date.today()
    horizon = today + timedelta(days=7)
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(today, horizon),
        )
    )
    items: list[AlertItem] = []
    for slot in result.scalars().all():
        booked_q = await db.execute(
            select(func.count()).where(
                Booking.event_slot_id == slot.id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
        booked = int(booked_q.scalar() or 0)
        # Use _get_service_limits to get capacity for the slot's services.
        # service_config is a list of {appointment_type_id, min_required, max_allowed}
        # — not a dict with a "services" key. Same convention as
        # app.services.availability._get_service_limits.
        capacity = 0
        for svc in (slot.service_config or []):
            try:
                capacity += int(svc.get("max_allowed", 0) or 0)
            except (TypeError, ValueError):
                continue
        if capacity == 0:
            continue
        fill_pct = booked / capacity
        if fill_pct >= 0.60:
            continue
        days_until = (slot.date - today).days
        urgency_severity = "high" if days_until <= 2 else "medium"
        items.append(AlertItem(
            id=f"at_risk:{slot.id}",
            source="at_risk_event",
            severity=urgency_severity,
            title=(
                f"{slot.label or 'Event'} is {int(fill_pct * 100)}% filled — "
                f"{days_until} day{'s' if days_until != 1 else ''} away"
            ),
            body=f"{booked} of {capacity} booked. Send reminders or start a wave.",
            cta_label="View event",
            cta_url=f"/run-sheet/{slot.id}",
            age_seconds=0,
            icon="AlertTriangle",
            accent="amber" if days_until > 2 else "red",
            context={"slot_id": str(slot.id), "fill_pct": round(fill_pct, 2)},
        ))
    # Cap to 5 to keep the inbox skimmable.
    return items[:5]


def _alerts_dummy_issue_reports(now: datetime) -> list[AlertItem]:
    """Placeholder items so the admin can see how the issue-reporting
    sources (complaint / hallucination / feedback) will render once the
    issue_report backend ships. Remove this function when wiring the real
    feed."""
    seed = [
        ("complaint",
         "Volunteer complaint — Mark R. (sample)",
         "“The reminder SMS arrived twice this morning.” Reply or dismiss.",
         "rose", "MessageSquareWarning", 8 * 60),
        ("hallucination",
         "Hallucination flag — thumbs-down on AI reply (sample)",
         "Volunteer flagged an AI reply as wrong. Open the conversation to "
         "review and patch the prompt.",
         "violet", "Sparkles", 35 * 60),
        ("feedback",
         "Feedback — Jamie L. (sample)",
         "“Loved the new check-in flow!” No action required; archive when done.",
         "blue", "MessagesSquare", 3 * 3600),
    ]
    items: list[AlertItem] = []
    for source, title, body, accent, icon, age in seed:
        items.append(AlertItem(
            id=f"dummy_{source}",
            source=f"issue_{source}",
            severity="low",
            title=title,
            body=body,
            cta_label="Open",
            cta_url="/conversations",
            age_seconds=age,
            icon=icon,
            accent=accent,
            context={"placeholder": True},
        ))
    return items


@router.get("/alerts", response_model=list[AlertItem])
async def list_alerts(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Unified Needs-You-Now feed.

    Ordering: severity rank first (high → low), then age descending so
    the freshest of each severity bubbles to the top within its band.

    Server-side filtering (Phase 2):
      - Alerts dismissed in dashboard_alert_state are dropped entirely.
      - Alerts with an active snooze (snoozed_until > now) are dropped
        for the duration of the snooze.
    """
    from app.models.dashboard_alert_state import (
        ALERT_STATE_DISMISSED,
        ALERT_STATE_SNOOZED,
        DashboardAlertState,
    )

    now = datetime.now(timezone.utc)

    state_rows = (await db.execute(
        select(DashboardAlertState).where(
            DashboardAlertState.tenant_id == tenant.id,
        )
    )).scalars().all()
    suppressed: set[str] = set()
    for row in state_rows:
        if row.state == ALERT_STATE_DISMISSED:
            suppressed.add(row.alert_id)
        elif row.state == ALERT_STATE_SNOOZED:
            if row.snoozed_until and row.snoozed_until > now:
                suppressed.add(row.alert_id)

    # Run sequentially, NOT via asyncio.gather. SQLAlchemy AsyncSession
    # is not concurrency-safe — running multiple await db.execute() calls
    # concurrently on the same session corrupts the underlying asyncpg
    # connection's transaction state, the connection goes back to the
    # pool wedged, and every subsequent request that grabs it fails
    # with "cannot use Connection.transaction() in a manually started
    # transaction". Sequential is the right pattern here; the dashboard
    # alerts already polls every 60s, not on the critical path.
    items: list[AlertItem] = []
    for fn in (
        _alerts_service_switches,
        _alerts_pending_reviews,
        _alerts_unreviewed_suspensions,
        _alerts_walkup_candidates,
        _alerts_at_risk_events,
    ):
        items.extend(await fn(db, tenant, now))
    items.extend(_alerts_dummy_issue_reports(now))

    items = [a for a in items if a.id not in suppressed]
    items.sort(key=lambda a: (_SEV_RANK.get(a.severity, 99), -a.age_seconds))
    return items


# ── Alert state (snooze / dismiss persistence) ──

class AlertStateAction(BaseModel):
    """POST body for snoozing or dismissing an alert."""
    alert_id: str
    state: str             # 'snoozed' | 'dismissed'
    snooze_hours: float | None = None
    dismiss_reason: str | None = None


class AlertStateRecord(BaseModel):
    """GET row in /alert-state — the active suppressions for this tenant."""
    alert_id: str
    state: str
    snoozed_until: datetime | None = None
    dismiss_reason: str | None = None
    created_at: datetime
    created_by_admin_id: uuid.UUID


@router.get("/alert-state", response_model=list[AlertStateRecord])
async def list_alert_state(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Return the alert-state rows for this tenant. The frontend uses this
    to reflect snooze countdowns and dismiss reasons in its UI even though
    the suppression itself happens server-side in /alerts."""
    from app.models.dashboard_alert_state import DashboardAlertState

    rows = (await db.execute(
        select(DashboardAlertState).where(
            DashboardAlertState.tenant_id == tenant.id,
        )
    )).scalars().all()
    return [
        AlertStateRecord(
            alert_id=r.alert_id,
            state=r.state,
            snoozed_until=r.snoozed_until,
            dismiss_reason=r.dismiss_reason,
            created_at=r.created_at,
            created_by_admin_id=r.created_by_admin_id,
        )
        for r in rows
    ]


@router.post("/alert-state", response_model=AlertStateRecord)
async def upsert_alert_state(
    body: AlertStateAction,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Snooze or dismiss a single alert.

    Upserts via ON CONFLICT (tenant_id, alert_id) so flipping an alert
    from snoozed → dismissed is a single round trip and the old state is
    replaced cleanly.
    """
    from app.models.dashboard_alert_state import (
        ALERT_STATE_DISMISSED,
        ALERT_STATE_SNOOZED,
        DashboardAlertState,
    )

    if body.state not in (ALERT_STATE_SNOOZED, ALERT_STATE_DISMISSED):
        raise HTTPException(
            status_code=400,
            detail=f"state must be one of 'snoozed', 'dismissed' (got {body.state!r})",
        )

    snoozed_until = None
    if body.state == ALERT_STATE_SNOOZED:
        if not body.snooze_hours or body.snooze_hours <= 0:
            raise HTTPException(
                status_code=400,
                detail="snooze_hours must be a positive number when state='snoozed'",
            )
        snoozed_until = datetime.now(timezone.utc) + timedelta(
            hours=body.snooze_hours
        )

    stmt = (
        pg_insert(DashboardAlertState)
        .values(
            tenant_id=tenant.id,
            alert_id=body.alert_id,
            state=body.state,
            snoozed_until=snoozed_until,
            dismiss_reason=body.dismiss_reason,
            created_by_admin_id=current_user.id,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "alert_id"],
            set_={
                "state": body.state,
                "snoozed_until": snoozed_until,
                "dismiss_reason": body.dismiss_reason,
                "created_by_admin_id": current_user.id,
                "created_at": datetime.now(timezone.utc),
            },
        )
        .returning(DashboardAlertState)
    )
    result = await db.execute(stmt)
    row = result.scalar_one()
    # No manual commit — the get_db dependency commits at end-of-request.
    # Calling commit() here would leave the asyncpg connection in a state
    # the SQLAlchemy session doesn't track cleanly.
    return AlertStateRecord(
        alert_id=row.alert_id,
        state=row.state,
        snoozed_until=row.snoozed_until,
        dismiss_reason=row.dismiss_reason,
        created_at=row.created_at,
        created_by_admin_id=row.created_by_admin_id,
    )


@router.delete("/alert-state/{alert_id}")
async def clear_alert_state(
    alert_id: str,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Clear any active state for an alert — used when an admin un-snoozes
    or wants a dismissed alert to come back."""
    from app.models.dashboard_alert_state import DashboardAlertState
    from sqlalchemy import delete as sql_delete

    await db.execute(
        sql_delete(DashboardAlertState).where(
            DashboardAlertState.tenant_id == tenant.id,
            DashboardAlertState.alert_id == alert_id,
        )
    )
    # No manual commit — the get_db dependency handles it.
    return {"ok": True}


# ── Planning view (T+8 → T+60) ──

class PlanningCampaignSummary(BaseModel):
    id: uuid.UUID
    status: str
    waves_total: int
    waves_completed: int


class PlanningEvent(BaseModel):
    slot_id: uuid.UUID
    label: str
    location: str | None
    date: date
    days_until: int
    bucket: str  # 'week_2' | 'weeks_3_4' | 'month_2'
    booked: int
    capacity: int
    fill_pct: float
    campaign: PlanningCampaignSummary | None = None
    health: str  # 'filled' | 'filling' | 'needs_campaign' | 'not_started'


@router.get("/planning", response_model=list[PlanningEvent])
async def get_planning_events(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Events in the T+8 → T+60 window, grouped by horizon bucket.

    Each event carries its campaign status (if any) and a derived health
    label the UI uses to color-code the row:
      - filled        : >= 100% booked → green
      - filling       : >= 60% booked OR active campaign making progress
      - needs_campaign: < 60% booked, no active campaign, < 21 days out
      - not_started   : > 21 days out, no campaign yet
    """
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
        RecruitmentWave,
        WaveStatus,
    )

    today = date.today()
    start = today + timedelta(days=8)
    end = today + timedelta(days=60)

    slots = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(start, end),
        ).order_by(SpecificDateSlot.date.asc())
    )).scalars().all()

    if not slots:
        return []

    slot_ids = [s.id for s in slots]

    # Booked counts per slot
    booked_rows = (await db.execute(
        select(Booking.event_slot_id, func.count())
        .where(
            Booking.tenant_id == tenant.id,
            Booking.event_slot_id.in_(slot_ids),
            Booking.status != BookingStatus.CANCELLED,
        )
        .group_by(Booking.event_slot_id)
    )).all()
    booked_by_slot = {sid: int(n) for sid, n in booked_rows}

    # Most-recent campaign per slot
    campaign_rows = (await db.execute(
        select(RecruitmentCampaign)
        .where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.event_slot_id.in_(slot_ids),
        )
        .order_by(RecruitmentCampaign.created_at.desc())
    )).scalars().all()
    campaign_by_slot: dict[uuid.UUID, RecruitmentCampaign] = {}
    for c in campaign_rows:
        # Keep the first (most recent) per slot
        campaign_by_slot.setdefault(c.event_slot_id, c)

    # Wave counts for the campaigns we picked
    relevant_campaign_ids = [c.id for c in campaign_by_slot.values()]
    waves_by_campaign: dict[uuid.UUID, tuple[int, int]] = {}
    if relevant_campaign_ids:
        wave_rows = (await db.execute(
            select(
                RecruitmentWave.campaign_id,
                func.count().label("total"),
                func.sum(
                    func.cast(
                        RecruitmentWave.status == WaveStatus.SENT, sa_int_one()
                    )
                ).label("done"),
            )
            .where(RecruitmentWave.campaign_id.in_(relevant_campaign_ids))
            .group_by(RecruitmentWave.campaign_id)
        )).all()
        for cid, total, done in wave_rows:
            waves_by_campaign[cid] = (int(total or 0), int(done or 0))

    out: list[PlanningEvent] = []
    for slot in slots:
        # service_config is a list of {appointment_type_id, min_required, max_allowed}
        # — not a dict with a "services" key. Same convention as
        # app.services.availability._get_service_limits.
        capacity = 0
        for svc in (slot.service_config or []):
            try:
                capacity += int(svc.get("max_allowed", 0) or 0)
            except (TypeError, ValueError):
                continue
        booked = booked_by_slot.get(slot.id, 0)
        fill_pct = (booked / capacity) if capacity > 0 else 0.0
        days_until = (slot.date - today).days

        if days_until <= 14:
            bucket = "week_2"
        elif days_until <= 28:
            bucket = "weeks_3_4"
        else:
            bucket = "month_2"

        camp = campaign_by_slot.get(slot.id)
        campaign_summary: PlanningCampaignSummary | None = None
        if camp is not None:
            wt, wd = waves_by_campaign.get(camp.id, (0, 0))
            campaign_summary = PlanningCampaignSummary(
                id=camp.id,
                status=str(camp.status.value if hasattr(camp.status, "value") else camp.status),
                waves_total=wt,
                waves_completed=wd,
            )

        # Health label
        if fill_pct >= 1.0:
            health = "filled"
        elif fill_pct >= 0.6:
            health = "filling"
        elif camp and campaign_summary and campaign_summary.status in (
            "active", "awaiting_approval", "draft"
        ):
            health = "filling"
        elif days_until <= 21:
            health = "needs_campaign"
        else:
            health = "not_started"

        out.append(PlanningEvent(
            slot_id=slot.id,
            label=slot.label or "(unnamed event)",
            location=slot.location,
            date=slot.date,
            days_until=days_until,
            bucket=bucket,
            booked=booked,
            capacity=capacity,
            fill_pct=round(fill_pct, 3),
            campaign=campaign_summary,
            health=health,
        ))
    return out


# ── Recommendations (rule-based, suggestive) ──

class Recommendation(BaseModel):
    id: str
    kind: str        # 'start_campaign' | 'push_wave' | 'over_recruit' | 'stagger'
    title: str
    body: str
    cta_label: str
    cta_url: str
    accent: str      # color hint
    context: dict | None = None


@router.get("/recommendations", response_model=list[Recommendation])
async def get_recommendations(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Rule-based planning recommendations.

    Phase 2 rules (no AI yet — the user said 'Suggestive', meaning the
    admin clicks Start, not auto-fire):
      1. start_campaign  : event 14-45 days out, no campaign yet, fill < 50%
      2. push_wave       : campaign exists but stalled (active > 5 days
                            since last send) and fill < 70%
      3. stagger         : 3+ events on the same day
    """
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
        RecruitmentWave,
        WaveStatus,
    )

    today = date.today()
    horizon_start = today + timedelta(days=8)
    horizon_end = today + timedelta(days=60)

    slots = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(horizon_start, horizon_end),
        ).order_by(SpecificDateSlot.date.asc())
    )).scalars().all()

    if not slots:
        return []

    slot_ids = [s.id for s in slots]
    booked_rows = (await db.execute(
        select(Booking.event_slot_id, func.count())
        .where(
            Booking.tenant_id == tenant.id,
            Booking.event_slot_id.in_(slot_ids),
            Booking.status != BookingStatus.CANCELLED,
        )
        .group_by(Booking.event_slot_id)
    )).all()
    booked_by_slot = {sid: int(n) for sid, n in booked_rows}

    campaigns = (await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.event_slot_id.in_(slot_ids),
        )
    )).scalars().all()
    campaign_by_slot: dict[uuid.UUID, RecruitmentCampaign] = {}
    for c in campaigns:
        campaign_by_slot[c.event_slot_id] = c

    recs: list[Recommendation] = []

    # Rule 1: start a campaign for under-filled events with no campaign yet
    for slot in slots:
        days_until = (slot.date - today).days
        if days_until < 14 or days_until > 45:
            continue
        if slot.id in campaign_by_slot:
            continue
        capacity = sum(
            int(s.get("max_allowed", 0) or 0)
            for s in (slot.service_config or [])
        )
        if capacity == 0:
            continue
        booked = booked_by_slot.get(slot.id, 0)
        if booked / capacity >= 0.5:
            continue
        recs.append(Recommendation(
            id=f"rec_start:{slot.id}",
            kind="start_campaign",
            title=f"Start a campaign for {slot.label or 'event'}",
            body=(
                f"{days_until} days out and only {booked} of {capacity} "
                f"booked. Recruitment waves take 1-3 weeks to land — start "
                f"now to fill comfortably."
            ),
            cta_label="Start campaign",
            cta_url=f"/campaigns?event_slot_id={slot.id}",
            accent="blue",
            context={
                "slot_id": str(slot.id),
                "days_until": days_until,
                "fill_pct": round(booked / capacity, 2),
            },
        ))

    # Rule 2: push next wave for stalled active campaigns
    if campaigns:
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        for camp in campaigns:
            status = camp.status.value if hasattr(camp.status, "value") else camp.status
            if str(status) != CampaignStatus.ACTIVE.value:
                continue
            slot = next((s for s in slots if s.id == camp.event_slot_id), None)
            if slot is None:
                continue
            capacity = sum(
                int(s.get("max_allowed", 0) or 0)
                for s in (slot.service_config or [])
            )
            if capacity == 0:
                continue
            booked = booked_by_slot.get(slot.id, 0)
            if booked / capacity >= 0.7:
                continue
            # Check last wave activity
            last_wave = (await db.execute(
                select(RecruitmentWave)
                .where(RecruitmentWave.campaign_id == camp.id)
                .order_by(RecruitmentWave.updated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if last_wave is None or (
                last_wave.updated_at and last_wave.updated_at > five_days_ago
            ):
                continue
            recs.append(Recommendation(
                id=f"rec_push:{camp.id}",
                kind="push_wave",
                title=f"Campaign stalled for {slot.label or 'event'}",
                body=(
                    f"Last wave moved 5+ days ago, only {booked} of "
                    f"{capacity} booked. Push the next wave to recover."
                ),
                cta_label="Open campaign",
                cta_url=f"/campaigns/{camp.id}",
                accent="amber",
                context={"campaign_id": str(camp.id)},
            ))

    # Rule 3: stagger same-day stacking (3+ events on one date)
    by_date: dict[date, list[SpecificDateSlot]] = {}
    for slot in slots:
        by_date.setdefault(slot.date, []).append(slot)
    for slot_date, group in by_date.items():
        if len(group) < 3:
            continue
        days_until = (slot_date - today).days
        recs.append(Recommendation(
            id=f"rec_stagger:{slot_date.isoformat()}",
            kind="stagger",
            title=(
                f"{len(group)} events stacked on "
                f"{slot_date.strftime('%a, %b %-d') if hasattr(slot_date, 'strftime') else slot_date}"
            ),
            body=(
                "Multi-event days historically have lower co-fill rates. "
                "Consider staggering campaigns or message templates so "
                "volunteers don't see overlapping asks."
            ),
            cta_label="Review the day",
            cta_url=f"/bookings?date={slot_date.isoformat()}",
            accent="violet",
            context={
                "date": slot_date.isoformat(),
                "event_count": len(group),
                "days_until": days_until,
            },
        ))

    return recs


# Small helper — cast bool to int in a portable way for SUM().
def sa_int_one():
    import sqlalchemy as sa
    return sa.Integer()
