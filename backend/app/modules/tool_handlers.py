"""Tool handler implementations for SMS tool_use conversations."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import cast, select, func, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement, AnnouncementStatus
from app.models.appointment_type import AppointmentType
from app.models.blocked_date import BlockedDate
from app.models.booking import Booking, BookingStatus
from app.models.booking_history import BookingHistory, BookingEventType, ChangedBy
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.contact_preferred_type import ContactPreferredType
from app.models.tenant import Tenant
from app.services.availability import (
    compute_available_slots,
    count_bookings_at_slot,
    get_service_limits_for_booking,
)
from app.services.booking import (
    process_booking_creation,
    process_booking_cancellation,
    process_booking_reschedule,
)
from app.models.notification import NotificationType
from app.services.notification import create_notification
from app.services.sms import send_sms

import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Shared context passed to all tool handlers within a single conversation turn."""

    db: AsyncSession
    tenant: Tenant
    contact_phone: str
    contact_id: uuid.UUID
    is_admin: bool
    test_mode: bool = False
    booking_created: bool = False
    booking_cancelled: bool = False
    booking_rescheduled: bool = False
    tool_calls: list = field(default_factory=list)


def _booking_ref(booking_id: uuid.UUID) -> str:
    """Generate short reference from booking UUID (last 8 hex chars)."""
    return str(booking_id).replace("-", "")[-8:]


async def _get_allowed_service_ids(ctx: ToolContext) -> list[uuid.UUID] | None:
    """Get the list of service IDs a volunteer is allowed to book.

    Returns:
        None — volunteer can book any service (all_services_enabled=True)
        list[UUID] — specific services allowed (may be empty = none allowed)
    """
    # Check if volunteer has all_services_enabled
    contact_result = await ctx.db.execute(
        select(Contact.all_services_enabled).where(Contact.id == ctx.contact_id)
    )
    all_services = contact_result.scalar_one_or_none()
    if all_services:
        return None  # All services allowed

    # Check specific assignments
    pref_result = await ctx.db.execute(
        select(ContactPreferredType.appointment_type_id).where(
            ContactPreferredType.contact_id == ctx.contact_id,
            ContactPreferredType.tenant_id == ctx.tenant.id,
        )
    )
    return list(pref_result.scalars().all())


async def _notify_unassigned_booking_attempt(ctx: ToolContext, service_name: str) -> None:
    """Send an admin notification when a volunteer tries to book an unassigned service."""
    # Look up volunteer name
    contact_result = await ctx.db.execute(
        select(Contact.name, Contact.phone).where(Contact.id == ctx.contact_id)
    )
    row = contact_result.one_or_none()
    vol_name = row.name if row and row.name else "Unknown"
    vol_phone = row.phone if row else ctx.contact_phone

    await create_notification(
        db=ctx.db,
        notification_type=NotificationType.UNASSIGNED_SERVICE,
        title=f"Unassigned service booking attempt: {vol_name}",
        body=(
            f"Volunteer {vol_name} ({vol_phone}) tried to book '{service_name}' "
            f"but has no services assigned. Please review their service assignments."
        ),
        tenant_id=ctx.tenant.id,
    )


async def _resolve_appointment_type(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> AppointmentType | None:
    """Resolve appointment type by name (case-insensitive)."""
    result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.tenant_id == tenant_id,
            AppointmentType.is_active.is_(True),
            func.lower(AppointmentType.name) == name.lower(),
        )
    )
    return result.scalar_one_or_none()


async def _resolve_booking_by_ref(
    db: AsyncSession, tenant_id: uuid.UUID, ref: str, contact_phone: str | None = None
) -> Booking | None:
    """Resolve booking by short reference code."""
    query = select(Booking).where(
        Booking.tenant_id == tenant_id,
        cast(Booking.id, String).like(f"%{ref}"),
        Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
    )
    if contact_phone:
        query = query.where(Booking.contact_phone == contact_phone)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# ── Handler implementations ──


async def handle_list_services(ctx: ToolContext, tool_input: dict) -> str:
    query = select(AppointmentType).where(
        AppointmentType.tenant_id == ctx.tenant.id,
        AppointmentType.is_active.is_(True),
    )
    # Filter by volunteer's allowed services (if not admin)
    if not ctx.is_admin:
        allowed_ids = await _get_allowed_service_ids(ctx)
        if allowed_ids is not None:
            if not allowed_ids:
                return json.dumps({"services": [], "message": "You do not have any services assigned yet. Please contact the administrator to get services assigned."})
            query = query.where(AppointmentType.id.in_(allowed_ids))
    result = await ctx.db.execute(query)
    types = list(result.scalars().all())

    # Pre-compute upcoming opportunities per service so the AI can give
    # the volunteer the *when* alongside the *what*. Without this, the
    # LLM lists service names with no event/date/time and the volunteer
    # has to ask a second question to learn when they can sign up.
    events_by_service = await _upcoming_events_per_service(ctx, types)

    items = []
    for t in types:
        entry = {
            "name": t.name,
            "duration_minutes": t.duration_minutes,
            "price": float(t.price),
            "description": t.description or "",
        }
        upcoming = events_by_service.get(t.id, [])
        if upcoming:
            entry["upcoming_events"] = upcoming
        items.append(entry)

    payload = {"services": items}
    if any(s.get("upcoming_events") for s in items):
        payload["presentation_hint"] = (
            "When telling the volunteer about each service, include the next "
            "upcoming event date/time/location from upcoming_events. Don't "
            "just list service names — share *where and when* they can help."
        )
    return json.dumps(payload)


async def _upcoming_events_per_service(
    ctx: ToolContext,
    types: list[AppointmentType],
    horizon_days: int = 28,
    per_service_limit: int = 3,
) -> dict[uuid.UUID, list[dict]]:
    """Return up to N upcoming events per service within the horizon.

    A service is "needed" at an event when the event's service_config
    JSONB either:
      - lists this appointment_type_id explicitly, OR
      - is NULL/empty (which means "all active services welcome" — see
        AvailabilityRule docstring)

    Pulls from both SpecificDateSlot (one-off events) and AvailabilityRule
    (recurring weekly windows — next 1-2 occurrences within horizon).
    Sorted by date+time, capped at per_service_limit.
    """
    from app.models.availability import AvailabilityRule, SpecificDateSlot

    if not types:
        return {}

    today = date.today()
    horizon_end = today + timedelta(days=horizon_days)
    type_ids = {t.id for t in types}

    # ── One-off events ──
    sds_rows = (
        await ctx.db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == ctx.tenant.id,
                SpecificDateSlot.is_active.is_(True),
                SpecificDateSlot.date >= today,
                SpecificDateSlot.date <= horizon_end,
            ).order_by(SpecificDateSlot.date.asc(), SpecificDateSlot.start_time.asc())
        )
    ).scalars().all()

    # ── Recurring weekly windows ──
    rules = (
        await ctx.db.execute(
            select(AvailabilityRule).where(
                AvailabilityRule.tenant_id == ctx.tenant.id,
                AvailabilityRule.is_active.is_(True),
            )
        )
    ).scalars().all()

    # Bucket: type_id -> list of {date, start, end, label, location, kind}
    by_service: dict[uuid.UUID, list[dict]] = {tid: [] for tid in type_ids}

    def _service_match(config: list | None, type_id: uuid.UUID) -> bool:
        """True when this event needs this service. NULL/empty config
        means all active services are welcome (per the model docstring)."""
        if not config:
            return True
        try:
            return any(
                str(entry.get("appointment_type_id")) == str(type_id)
                for entry in config
                if isinstance(entry, dict)
            )
        except (AttributeError, TypeError):
            return False

    def _fmt_time(t) -> str:
        return t.strftime("%I:%M %p").lstrip("0")

    # Process one-off slots
    for slot in sds_rows:
        for tid in type_ids:
            if _service_match(slot.service_config, tid):
                by_service[tid].append({
                    "date": slot.date.isoformat(),
                    "start": _fmt_time(slot.start_time),
                    "end": _fmt_time(slot.end_time),
                    "label": slot.label or None,
                    "location": slot.location or None,
                    "kind": "one_off",
                    "_sort_key": (slot.date, slot.start_time),
                })

    # Process recurring rules — emit next 2 occurrences within horizon
    for rule in rules:
        for tid in type_ids:
            if not _service_match(rule.service_config, tid):
                continue
            occurrences_added = 0
            for offset in range(horizon_days + 1):
                if occurrences_added >= 2:
                    break
                candidate = today + timedelta(days=offset)
                if candidate.weekday() != rule.day_of_week:
                    continue
                by_service[tid].append({
                    "date": candidate.isoformat(),
                    "start": _fmt_time(rule.start_time),
                    "end": _fmt_time(rule.end_time),
                    "label": rule.label or None,
                    "location": rule.location or None,
                    "kind": "recurring",
                    "_sort_key": (candidate, rule.start_time),
                })
                occurrences_added += 1

    # Sort each service's events and cap at limit; strip internal _sort_key
    for tid, events in by_service.items():
        events.sort(key=lambda e: e["_sort_key"])
        trimmed = events[:per_service_limit]
        for e in trimmed:
            e.pop("_sort_key", None)
            # Drop None-valued keys so the JSON stays compact for SMS
            for k in list(e.keys()):
                if e[k] is None:
                    del e[k]
        by_service[tid] = trimmed

    return by_service


async def _slot_allow_roster_sharing(
    ctx: ToolContext, target_date, start_t, end_t
) -> bool:
    """Return whether this slot's source rule/slot permits roster sharing.

    Specific-date events take precedence over weekly rules. Default to True if
    no covering source is found.
    """
    from app.models.availability import AvailabilityRule, SpecificDateSlot

    sd = (await ctx.db.execute(
        select(SpecificDateSlot.allow_roster_sharing).where(
            SpecificDateSlot.tenant_id == ctx.tenant.id,
            SpecificDateSlot.date == target_date,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.start_time <= start_t,
            SpecificDateSlot.end_time >= end_t,
        ).limit(1)
    )).scalar_one_or_none()
    if sd is not None:
        return bool(sd)

    wr = (await ctx.db.execute(
        select(AvailabilityRule.allow_roster_sharing).where(
            AvailabilityRule.tenant_id == ctx.tenant.id,
            AvailabilityRule.day_of_week == target_date.weekday(),
            AvailabilityRule.is_active.is_(True),
            AvailabilityRule.start_time <= start_t,
            AvailabilityRule.end_time >= end_t,
        ).limit(1)
    )).scalar_one_or_none()
    if wr is not None:
        return bool(wr)
    return True


def _format_roster_name(name: str | None, phone: str, visibility: str) -> str | None:
    """Apply visibility to a roster entry. Returns None when hidden."""
    if visibility == "hidden":
        return None
    display = (name or "").strip() or phone
    if visibility == "first_name":
        first = display.split()[0] if display else display
        return first
    return display  # full_name


async def _fetch_slot_roster(
    ctx: ToolContext, appt_type_id, slot_start, duration_minutes
) -> list[dict]:
    """Bookings on this slot with their roster_visibility, joined with contact."""
    slot_end = slot_start + timedelta(minutes=duration_minutes)
    rows = (await ctx.db.execute(
        select(
            Contact.name,
            Contact.phone,
            Booking.roster_visibility,
        )
        .join(Contact, Contact.id == Booking.contact_id)
        .where(
            Booking.tenant_id == ctx.tenant.id,
            Booking.appointment_type_id == appt_type_id,
            Booking.scheduled_at >= slot_start,
            Booking.scheduled_at < slot_end,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )).all()
    return [
        {"name": n, "phone": p, "visibility": v if isinstance(v, str) else (v.value if v else "first_name")}
        for (n, p, v) in rows
    ]


async def handle_check_availability(ctx: ToolContext, tool_input: dict) -> str:
    try:
        target_date = date.fromisoformat(tool_input["date"])
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    service_name = tool_input.get("service_name")

    # Pre-load any specific-date events on this date so we can attach
    # event_label / event_description to each slot a volunteer asks about.
    # The AI uses these so it can answer "what's this event about?"
    # without needing a separate tool call.
    from app.models.availability import SpecificDateSlot as _SDS
    specific_q = await ctx.db.execute(
        select(_SDS).where(
            _SDS.tenant_id == ctx.tenant.id,
            _SDS.date == target_date,
            _SDS.is_active.is_(True),
        )
    )
    specific_slots_today = list(specific_q.scalars().all())

    def _event_meta_for(start_t):
        """Return (label, description, location) for the event window containing
        the given slot start time, if any."""
        for s in specific_slots_today:
            if s.start_time <= start_t < s.end_time:
                return (s.label, s.description, s.location)
        return (None, None, None)

    # Get volunteer's allowed services (if not admin)
    allowed_ids = None
    if not ctx.is_admin:
        allowed_ids = await _get_allowed_service_ids(ctx)
        if allowed_ids is not None and not allowed_ids:
            return json.dumps({"error": "You do not have any services assigned yet. Please contact the administrator to get services assigned."})

    # Get appointment types to check
    query = select(AppointmentType).where(
        AppointmentType.tenant_id == ctx.tenant.id,
        AppointmentType.is_active.is_(True),
    )
    if service_name:
        query = query.where(func.lower(AppointmentType.name) == service_name.lower())
    if allowed_ids is not None:
        query = query.where(AppointmentType.id.in_(allowed_ids))
    result = await ctx.db.execute(query)
    types = result.scalars().all()

    if not types:
        if service_name:
            return json.dumps({"error": f"Service '{service_name}' is not available for you."})
        return json.dumps({"error": "No services available for you."})

    all_slots = []
    for appt_type in types:
        slots = await compute_available_slots(
            ctx.db, target_date, appt_type.id, ctx.tenant, max_slots=5
        )
        for slot in slots:
            start = slot["start"]
            booked = slot.get("booked", 0)
            min_req = slot.get("min_required", 1)
            max_allow = slot.get("max_allowed", 1)
            remaining = max_allow - booked
            needs_more = max(0, min_req - booked)
            slot_info = {
                "service": appt_type.name,
                "time": start.strftime("%I:%M %p"),
                "price": float(appt_type.price),
                "max_volunteers": max_allow,
                "signed_up": booked,
                "spots_remaining": remaining,
            }
            if needs_more > 0:
                slot_info["needs_more_to_confirm"] = needs_more

            # Attach event metadata when this slot belongs to a one-off
            # event on this date. The description gives the AI enough
            # context to answer volunteer questions like "what is this?"
            ev_label, ev_desc, ev_location = _event_meta_for(start.time())
            if ev_label:
                slot_info["event_label"] = ev_label
            if ev_desc:
                slot_info["event_description"] = ev_desc
            if ev_location:
                slot_info["event_location"] = ev_location

            if booked > 0:
                slot_end_t = (start + timedelta(minutes=appt_type.duration_minutes)).time()
                if ctx.is_admin:
                    # Admins always see the full roster, regardless of event-level sharing
                    # or per-booking visibility — they need to know who's coming.
                    roster_rows = await _fetch_slot_roster(
                        ctx, appt_type.id, start, appt_type.duration_minutes
                    )
                    # Format as "Name (phone)" so the LLM rendering on the
                    # admin side surfaces both — names alone are easy to
                    # confuse when two volunteers share a first name, and
                    # phone alone reads as anonymous. When the contact has
                    # no name yet, the phone stands on its own.
                    names: list[str] = []
                    for r in roster_rows:
                        nm = (r["name"] or "").strip()
                        phone = r["phone"]
                        names.append(f"{nm} ({phone})" if nm else phone)
                    if names:
                        slot_info["who_signed_up"] = names
                else:
                    allow_share = await _slot_allow_roster_sharing(
                        ctx, target_date, start.time(), slot_end_t
                    )
                    if allow_share:
                        roster_rows = await _fetch_slot_roster(
                            ctx, appt_type.id, start, appt_type.duration_minutes
                        )
                        names: list[str] = []
                        hidden_count = 0
                        for r in roster_rows:
                            formatted = _format_roster_name(
                                r["name"], r["phone"], r["visibility"]
                            )
                            if formatted is None:
                                hidden_count += 1
                            else:
                                names.append(formatted)
                        if names:
                            slot_info["who_signed_up"] = names
                        if hidden_count > 0:
                            slot_info["hidden_signups"] = hidden_count

            all_slots.append(slot_info)

    if not all_slots:
        return json.dumps({"message": f"No available slots on {target_date.strftime('%A %B %d')}."})

    return json.dumps({"date": tool_input["date"], "slots": all_slots})


async def handle_get_event_roster(ctx: ToolContext, tool_input: dict) -> str:
    """Return every active signup for one event, across ALL services and
    time windows. The piece check_availability misses by design (it slices
    per-time-slot, so a sign-up at 1pm is invisible to a 4pm slot query).

    For volunteers, applies the slot's allow_roster_sharing flag AND each
    booking's roster_visibility — hidden bookings get counted into a
    hidden_signups bucket so the LLM can say "and 2 others kept private".
    For admins, returns "Full Name (phone)" strings (same shape as
    check_availability's admin who_signed_up array)."""
    from app.models.availability import SpecificDateSlot
    from app.models.appointment_type import AppointmentType

    label_raw = (tool_input.get("event_label") or "").strip()
    date_str = tool_input.get("event_date")

    if not label_raw and not date_str:
        return json.dumps(
            {"error": "Provide event_label or event_date so I can find the event."}
        )

    target_date: date | None = None
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    label_lc = label_raw.lower()

    # Resolve slot. Prefer date + label; fall back to label-only across the
    # next 90 days; bail with clarification when multiple match.
    slot_q = select(SpecificDateSlot).where(
        SpecificDateSlot.tenant_id == ctx.tenant.id,
        SpecificDateSlot.is_active.is_(True),
    )
    if target_date is not None:
        slot_q = slot_q.where(SpecificDateSlot.date == target_date)
    else:
        # Upcoming window only — avoids ambiguity with old occurrences.
        slot_q = slot_q.where(
            SpecificDateSlot.date >= date.today(),
            SpecificDateSlot.date <= date.today() + timedelta(days=90),
        )
    candidates = (await ctx.db.execute(slot_q.order_by(SpecificDateSlot.date.asc()))).scalars().all()

    if label_lc:
        candidates = [c for c in candidates if label_lc in (c.label or "").lower()]

    if not candidates:
        return json.dumps({
            "message": (
                f"No event found matching {label_raw!r}"
                + (f" on {date_str}" if date_str else "")
                + "."
            ),
        })
    if len(candidates) > 1 and not target_date:
        # Multiple dates match → tell the LLM which to pick from.
        options = [
            {"label": c.label, "date": c.date.isoformat()} for c in candidates[:5]
        ]
        return json.dumps({
            "needs_clarification": True,
            "message": "Multiple events match — narrow by date.",
            "options": options,
        })

    slot = candidates[0]

    # Non-admin volunteers respect the slot's allow_roster_sharing flag.
    if not ctx.is_admin and not slot.allow_roster_sharing:
        return json.dumps({
            "event_label": slot.label,
            "event_date": slot.date.isoformat(),
            "message": "The organizer has set this event's roster to private.",
        })

    # Pull every active booking tied to this slot, joined to contact +
    # appointment type. event_slot_id is the canonical link; using it
    # picks up bookings regardless of which time window inside the event
    # they're at.
    rows = (await ctx.db.execute(
        select(Booking, Contact, AppointmentType)
        .join(Contact, Contact.id == Booking.contact_id)
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .where(
            Booking.tenant_id == ctx.tenant.id,
            Booking.event_slot_id == slot.id,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
        .order_by(AppointmentType.name, Booking.scheduled_at)
    )).all()

    by_service: dict[str, list[str]] = {}
    hidden_count = 0
    total_visible = 0
    for booking, contact, appt in rows:
        if ctx.is_admin:
            nm = (contact.name or "").strip()
            display = f"{nm} ({contact.phone})" if nm else contact.phone
        else:
            vis_raw = booking.roster_visibility
            vis = (
                vis_raw if isinstance(vis_raw, str)
                else (vis_raw.value if vis_raw else "first_name")
            )
            display = _format_roster_name(contact.name, contact.phone, vis)
            if display is None:
                hidden_count += 1
                continue
        by_service.setdefault(appt.name, []).append(display)
        total_visible += 1

    services_out = [
        {"service": name, "signups": names}
        for name, names in by_service.items()
    ]

    payload: dict = {
        "event_label": slot.label,
        "event_date": slot.date.isoformat(),
        "event_time": (
            f"{slot.start_time.strftime('%I:%M %p').lstrip('0')}"
            f"–{slot.end_time.strftime('%I:%M %p').lstrip('0')}"
        ),
        "services": services_out,
        "total_signups": total_visible + hidden_count,
        "visible_signups": total_visible,
    }
    if not ctx.is_admin and hidden_count > 0:
        payload["hidden_signups"] = hidden_count
    if total_visible == 0 and hidden_count == 0:
        payload["message"] = (
            f"No one has signed up for {slot.label or 'this event'} yet."
        )
    return json.dumps(payload)


async def handle_get_my_appointments(ctx: ToolContext, tool_input: dict) -> str:
    result = await ctx.db.execute(
        select(Booking)
        .where(
            Booking.tenant_id == ctx.tenant.id,
            Booking.contact_phone == ctx.contact_phone,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
            Booking.scheduled_at >= datetime.now(timezone.utc),
        )
        .order_by(Booking.scheduled_at)
    )
    bookings = result.scalars().all()

    items = []
    for b in bookings:
        appt = await ctx.db.execute(
            select(AppointmentType).where(AppointmentType.id == b.appointment_type_id)
        )
        appt_type = appt.scalar_one_or_none()
        items.append({
            "ref": _booking_ref(b.id),
            "service": appt_type.name if appt_type else "Unknown",
            "date": b.scheduled_at.strftime("%A %B %d"),
            "time": b.scheduled_at.strftime("%I:%M %p"),
            "price": float(b.price_at_booking),
            "status": b.status.value,
        })

    if not items:
        return json.dumps({"message": "You have no upcoming appointments."})
    return json.dumps({"appointments": items})


async def handle_book_appointment(ctx: ToolContext, tool_input: dict) -> str:
    from app.models.booking import RosterVisibility

    service_name = tool_input.get("service_name", "")
    date_str = tool_input.get("date", "")
    time_str = tool_input.get("time", "")

    # Resolve roster visibility:
    #   1. Explicit tool_input.share_on_roster wins (and is persisted as the
    #      contact's new default — answering once carries forward).
    #   2. Otherwise fall back to the contact's saved default_roster_visibility.
    #   3. Otherwise fall back to first_name (existing hardcoded default).
    explicit_visibility = tool_input.get("share_on_roster")
    contact_row: Contact | None = None
    if ctx.contact_id is not None:
        contact_row = (
            await ctx.db.execute(
                select(Contact).where(Contact.id == ctx.contact_id)
            )
        ).scalar_one_or_none()

    if explicit_visibility is not None:
        raw_visibility = explicit_visibility
    elif contact_row and contact_row.default_roster_visibility:
        raw_visibility = contact_row.default_roster_visibility
    else:
        # Privacy-first default: until the volunteer states a preference,
        # they're hidden from the public roster. Admins still see them
        # in full — admin roster fetchers bypass _format_roster_name.
        # When the volunteer later says "show my first name" / "use my
        # full name", that explicit pick gets persisted as their
        # default and carries forward.
        raw_visibility = "hidden"

    try:
        roster_visibility = RosterVisibility(raw_visibility)
    except ValueError:
        return json.dumps({
            "error": "share_on_roster must be 'hidden', 'first_name', or 'full_name'.",
        })

    # Persist the explicit pick as the contact's default so they aren't
    # re-asked on every future booking. Only writes when the value actually
    # differs from what's stored — avoids a no-op UPDATE on every booking.
    # When the value changes, also stash a ContactPreferenceHistory row
    # to be linked to the booking once it has an id (see below). Admins
    # see this on the Volunteer detail page as a timeline of stated
    # preferences.
    preference_change_pending: dict | None = None
    if (
        explicit_visibility is not None
        and contact_row is not None
        and contact_row.default_roster_visibility != roster_visibility.value
    ):
        previous = contact_row.default_roster_visibility
        contact_row.default_roster_visibility = roster_visibility.value
        preference_change_pending = {
            "previous": previous,
            "new": roster_visibility.value,
        }

    appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, service_name)
    if not appt_type:
        return json.dumps({"error": f"Service '{service_name}' not found."})

    # Block booking when a background check is required for this volunteer
    if not ctx.is_admin:
        bg_required = (await ctx.db.execute(
            select(Contact.background_check_required).where(Contact.id == ctx.contact_id)
        )).scalar()
        if bg_required:
            return json.dumps({
                "error": "A background check is required before you can book any appointments. Please contact the administrator.",
            })

    # Check volunteer is allowed to book this type
    if not ctx.is_admin:
        allowed_ids = await _get_allowed_service_ids(ctx)
        if allowed_ids is not None:
            if not allowed_ids:
                # No services assigned at all — notify admin
                await _notify_unassigned_booking_attempt(ctx, service_name)
                return json.dumps({"error": "You do not have any services assigned yet. Please contact the administrator to get services assigned."})
            if appt_type.id not in allowed_ids:
                # Has some services but not this one — notify admin
                await _notify_unassigned_booking_attempt(ctx, service_name)
                return json.dumps({"error": f"You are not registered to participate in '{service_name}'. Please contact the administrator."})

    try:
        scheduled_at = datetime.fromisoformat(f"{date_str}T{time_str}:00")
        # Apply tenant timezone
        import zoneinfo
        tz = zoneinfo.ZoneInfo(ctx.tenant.business_timezone or "America/New_York")
        scheduled_at = scheduled_at.replace(tzinfo=tz)
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date or time format."})

    # Block volunteers from holding two overlapping bookings — they can't be
    # in two places at once. Admins booking on behalf of others can also hit
    # this; that's still the right call (e.g. a volunteer can't physically
    # work two services at the same minute).
    if not ctx.is_admin and ctx.contact_id is not None:
        from app.services.booking import find_volunteer_overlap

        conflict = await find_volunteer_overlap(
            ctx.db, ctx.tenant.id, ctx.contact_id, scheduled_at, appt_type.duration_minutes
        )
        if conflict is not None:
            existing_booking, existing_type = conflict
            existing_end = existing_booking.scheduled_at + timedelta(
                minutes=existing_type.duration_minutes
            )
            return json.dumps({
                "error": "overlap_with_existing_booking",
                "message": (
                    f"This volunteer is already booked for '{existing_type.name}' from "
                    f"{existing_booking.scheduled_at.strftime('%I:%M %p')} to "
                    f"{existing_end.strftime('%I:%M %p')} on "
                    f"{existing_booking.scheduled_at.strftime('%A %B %d')}, "
                    f"which overlaps this slot."
                ),
                "conflicting_booking_ref": _booking_ref(existing_booking.id),
                "conflicting_service": existing_type.name,
                "conflicting_start": existing_booking.scheduled_at.strftime("%I:%M %p"),
                "conflicting_end": existing_end.strftime("%I:%M %p"),
                "conflicting_date": existing_booking.scheduled_at.strftime("%A %B %d"),
                "instruction_for_assistant": (
                    "Do NOT silently book either service. Tell the volunteer the two "
                    "services overlap (mention both service names and times), and ask "
                    "whether they want to keep the existing booking, cancel it and book "
                    "this new one, or pick a different time. Wait for their answer "
                    "before calling book_appointment or cancel_appointment."
                ),
            })

    # Check slot capacity before booking
    min_required, max_allowed = await get_service_limits_for_booking(
        ctx.db, ctx.tenant, str(appt_type.id), scheduled_at
    )
    current_count = await count_bookings_at_slot(
        ctx.db, ctx.tenant.id, str(appt_type.id), scheduled_at, appt_type.duration_minutes
    )
    if current_count >= max_allowed:
        # Suggest alternative slots
        alt_slots = await compute_available_slots(
            ctx.db, scheduled_at.date(), appt_type.id, ctx.tenant, max_slots=3
        )
        alternatives = [
            {"time": s["start"].strftime("%I:%M %p"), "date": s["start"].strftime("%A %B %d")}
            for s in alt_slots
        ]
        return json.dumps({
            "error": "This time slot is fully booked.",
            "max_allowed": max_allowed,
            "current_bookings": current_count,
            "alternative_slots": alternatives,
        })

    if max_allowed == 0:
        return json.dumps({
            "error": f"'{appt_type.name}' is not available during this time slot.",
        })

    # Resolve the event slot (if any) so the booking links to its
    # specific-date event by FK. Regular-availability bookings get
    # event_slot_id=None and aren't affected by slot-edit cascades.
    from app.services.booking import find_slot_for_booking
    event_slot = await find_slot_for_booking(
        ctx.db, ctx.tenant.id, scheduled_at, appt_type.id
    )

    # Create booking
    booking = Booking(
        tenant_id=ctx.tenant.id,
        contact_id=ctx.contact_id,
        contact_phone=ctx.contact_phone,
        appointment_type_id=appt_type.id,
        event_slot_id=event_slot.id if event_slot else None,
        scheduled_at=scheduled_at,
        price_at_booking=float(appt_type.price),
        status=BookingStatus.SCHEDULED,
        roster_visibility=roster_visibility.value,
        confirmed_at=datetime.now(timezone.utc),
    )
    ctx.db.add(booking)
    await ctx.db.flush()

    # Record history
    history = BookingHistory(
        booking_id=booking.id,
        event_type=BookingEventType.CREATED,
        new_status=BookingStatus.SCHEDULED,
        new_scheduled_at=scheduled_at,
        changed_by=ChangedBy.USER_SMS if not ctx.is_admin else ChangedBy.ADMIN,
        tenant_id=ctx.tenant.id,
    )
    ctx.db.add(history)

    # Tie the visibility-preference change to this booking now that we
    # have an id. Append-only row admins can see on the Volunteer page.
    if preference_change_pending is not None:
        from app.models.contact_preference_history import (
            PREFERENCE_FIELD_ROSTER_VISIBILITY,
            PREFERENCE_SOURCE_ADMIN,
            PREFERENCE_SOURCE_USER_SMS,
            ContactPreferenceHistory,
        )
        ctx.db.add(ContactPreferenceHistory(
            tenant_id=ctx.tenant.id,
            contact_id=ctx.contact_id,
            field=PREFERENCE_FIELD_ROSTER_VISIBILITY,
            previous_value=preference_change_pending["previous"],
            new_value=preference_change_pending["new"],
            source=(
                PREFERENCE_SOURCE_ADMIN
                if ctx.is_admin
                else PREFERENCE_SOURCE_USER_SMS
            ),
            source_booking_id=booking.id,
        ))

    # Process calendar + ICS (no SMS — Claude's response is the confirmation)
    try:
        await process_booking_creation(ctx.db, booking, ctx.tenant, send_sms_notification=False)
    except Exception as e:
        logger.error("process_booking_creation failed (booking still saved): %s", e)

    ctx.booking_created = True

    base_url = f"https://{ctx.tenant.api_domain}/api/v1/calendar/{booking.id}"

    # Surface the roster-visibility hint so the assistant can include it
    # in the booking confirmation reply. Volunteer should know how they
    # appear AND how to change it — they won't get re-asked otherwise.
    full_name = (contact_row.name or "").strip() if contact_row else ""
    first_name = full_name.split()[0] if full_name else ""
    roster_display_map = {
        "first_name": f"first name only ({first_name})" if first_name else "first name only",
        "full_name": f"full name ({full_name})" if full_name else "full name",
        "hidden": "hidden (not shown to other volunteers)",
    }
    roster_display = roster_display_map.get(
        roster_visibility.value, roster_visibility.value
    )
    from app.prompts.conversation import get_customer_booking_roster_hint_prompt
    hint_template = await get_customer_booking_roster_hint_prompt(
        ctx.db, ctx.tenant.id
    )
    roster_hint = hint_template.replace("{roster_display}", roster_display)

    return json.dumps({
        "success": True,
        "ref": _booking_ref(booking.id),
        "service": appt_type.name,
        "date": scheduled_at.strftime("%A %B %d"),
        "time": scheduled_at.strftime("%I:%M %p"),
        "price": float(appt_type.price),
        "calendar_link": f"{base_url}/new.ics",
        "roster_visibility_used": roster_visibility.value,
        "roster_display": roster_display,
        "roster_confirmation_hint": roster_hint,
        "assistant_instruction": (
            "Include the roster_confirmation_hint verbatim in your "
            "confirmation reply (one short paragraph after the booking "
            "details) so the volunteer knows how they appear on the "
            "roster and how to change it."
        ),
    })


async def handle_cancel_appointment(ctx: ToolContext, tool_input: dict) -> str:
    ref = tool_input.get("booking_ref", "")
    # Admins can cancel any booking; customers only their own
    phone_filter = None if ctx.is_admin else ctx.contact_phone
    booking = await _resolve_booking_by_ref(ctx.db, ctx.tenant.id, ref, phone_filter)

    if not booking:
        return json.dumps({"error": f"No active booking found with reference '{ref}'."})

    booking.status = BookingStatus.CANCELLED
    history = BookingHistory(
        booking_id=booking.id,
        event_type=BookingEventType.STATUS_CHANGED,
        new_status=BookingStatus.CANCELLED,
        changed_by=ChangedBy.USER_SMS if not ctx.is_admin else ChangedBy.ADMIN,
        tenant_id=ctx.tenant.id,
    )
    ctx.db.add(history)
    await ctx.db.flush()

    try:
        await process_booking_cancellation(ctx.db, booking, ctx.tenant, send_sms_notification=False)
    except Exception as e:
        logger.error("process_booking_cancellation failed: %s", e)
    ctx.booking_cancelled = True

    base_url = f"https://{ctx.tenant.api_domain}/api/v1/calendar/{booking.id}"

    return json.dumps({
        "success": True,
        "ref": ref,
        "message": "Appointment has been cancelled.",
        "calendar_link": f"{base_url}/cancel.ics",
    })


async def handle_reschedule_appointment(ctx: ToolContext, tool_input: dict) -> str:
    ref = tool_input.get("booking_ref", "")
    new_date = tool_input.get("new_date", "")
    new_time = tool_input.get("new_time", "")

    phone_filter = None if ctx.is_admin else ctx.contact_phone
    booking = await _resolve_booking_by_ref(ctx.db, ctx.tenant.id, ref, phone_filter)

    if not booking:
        return json.dumps({"error": f"No active booking found with reference '{ref}'."})

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(ctx.tenant.business_timezone or "America/New_York")
        new_scheduled = datetime.fromisoformat(f"{new_date}T{new_time}:00").replace(tzinfo=tz)
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date or time format."})

    booking.scheduled_at = new_scheduled
    booking.status = BookingStatus.RESCHEDULED
    booking.ics_sequence = (booking.ics_sequence or 0) + 1
    # Re-resolve the event slot — a reschedule across days can move the
    # booking onto a different event (or off any event onto regular
    # availability). Without this, event_slot_id would point at the
    # previous event and the new event's roster wouldn't include this
    # booking.
    from app.services.booking import find_slot_for_booking
    new_slot = await find_slot_for_booking(
        ctx.db, ctx.tenant.id, new_scheduled, booking.appointment_type_id
    )
    booking.event_slot_id = new_slot.id if new_slot else None

    history = BookingHistory(
        booking_id=booking.id,
        event_type=BookingEventType.RESCHEDULED,
        new_status=BookingStatus.RESCHEDULED,
        new_scheduled_at=new_scheduled,
        changed_by=ChangedBy.USER_SMS if not ctx.is_admin else ChangedBy.ADMIN,
        tenant_id=ctx.tenant.id,
    )
    ctx.db.add(history)
    await ctx.db.flush()

    try:
        await process_booking_reschedule(ctx.db, booking, ctx.tenant, send_sms_notification=False)
    except Exception as e:
        logger.error("process_booking_reschedule failed: %s", e)
    ctx.booking_rescheduled = True

    base_url = f"https://{ctx.tenant.api_domain}/api/v1/calendar/{booking.id}"

    return json.dumps({
        "success": True,
        "ref": ref,
        "new_date": new_scheduled.strftime("%A %B %d"),
        "new_time": new_scheduled.strftime("%I:%M %p"),
        "calendar_link": f"{base_url}/update.ics",
    })


# ── Admin-only handlers ──


async def handle_search_bookings(ctx: ToolContext, tool_input: dict) -> str:
    query = select(Booking).where(Booking.tenant_id == ctx.tenant.id)

    if tool_input.get("date"):
        try:
            target = date.fromisoformat(tool_input["date"])
            query = query.where(
                func.date(Booking.scheduled_at) == target
            )
        except ValueError:
            return json.dumps({"error": "Invalid date format."})

    if tool_input.get("status"):
        try:
            status = BookingStatus(tool_input["status"])
            query = query.where(Booking.status == status)
        except ValueError:
            return json.dumps({"error": f"Invalid status. Use: {', '.join(s.value for s in BookingStatus)}"})

    if tool_input.get("customer_phone"):
        query = query.where(Booking.contact_phone.ilike(f"%{tool_input['customer_phone']}%"))

    query = query.order_by(Booking.scheduled_at.desc()).limit(20)
    result = await ctx.db.execute(query)
    bookings = result.scalars().all()

    items = []
    for b in bookings:
        appt = await ctx.db.execute(
            select(AppointmentType).where(AppointmentType.id == b.appointment_type_id)
        )
        appt_type = appt.scalar_one_or_none()
        items.append({
            "ref": _booking_ref(b.id),
            "customer_phone": b.contact_phone,
            "service": appt_type.name if appt_type else "Unknown",
            "date": b.scheduled_at.strftime("%A %B %d"),
            "time": b.scheduled_at.strftime("%I:%M %p"),
            "price": float(b.price_at_booking),
            "status": b.status.value,
        })

    if not items:
        return json.dumps({"message": "No bookings found matching your criteria."})
    return json.dumps({"bookings": items, "total": len(items)})


async def handle_lookup_customer(ctx: ToolContext, tool_input: dict) -> str:
    query = select(Contact).where(Contact.tenant_id == ctx.tenant.id)

    phone = tool_input.get("phone")
    name = tool_input.get("name")

    if phone:
        query = query.where(Contact.phone.ilike(f"%{phone}%"))
    elif name:
        query = query.where(Contact.name.ilike(f"%{name}%"))
    else:
        return json.dumps({"error": "Provide a phone number or name to search."})

    query = query.limit(10)
    result = await ctx.db.execute(query)
    contacts = result.scalars().all()

    items = []
    for c in contacts:
        # Get booking count
        count_result = await ctx.db.execute(
            select(func.count()).select_from(Booking).where(
                Booking.contact_id == c.id,
                Booking.tenant_id == ctx.tenant.id,
            )
        )
        booking_count = count_result.scalar() or 0

        # Get consent status
        consent_result = await ctx.db.execute(
            select(ContactConsent).where(
                ContactConsent.contact_id == c.id,
                ContactConsent.tenant_id == ctx.tenant.id,
            )
        )
        consent = consent_result.scalar_one_or_none()

        items.append({
            "phone": c.phone,
            "name": c.name or "—",
            "email": c.email or "—",
            "status": c.status.value if c.status else "active",
            "consent": consent.status.value if consent else "unknown",
            "total_bookings": booking_count,
        })

    if not items:
        return json.dumps({"message": "No customers found."})
    return json.dumps({"customers": items})


async def _resolve_service_ids_by_name(ctx: ToolContext, names: list[str]):
    """Map a list of service names to AppointmentType ids. Returns (ids, error_dict_or_None)."""
    if not names:
        return [], None
    out = []
    for n in names:
        appt = await _resolve_appointment_type(ctx.db, ctx.tenant.id, n)
        if not appt:
            return None, {"error": f"Service '{n}' not found."}
        out.append(appt.id)
    return out, None


async def _sync_volunteer_services(ctx: ToolContext, contact_id, type_ids: list):
    from sqlalchemy import delete as sql_delete
    await ctx.db.execute(
        sql_delete(ContactPreferredType).where(
            ContactPreferredType.contact_id == contact_id,
            ContactPreferredType.tenant_id == ctx.tenant.id,
        )
    )
    for tid in type_ids:
        ctx.db.add(
            ContactPreferredType(
                tenant_id=ctx.tenant.id,
                contact_id=contact_id,
                appointment_type_id=tid,
            )
        )
    await ctx.db.flush()


def _normalize_weekly_hours(rows: list | None) -> tuple[list | None, dict | None]:
    """Validate and JSON-serialize weekly_hours blocks. Returns (normalized, error_dict_or_None)."""
    if rows is None:
        return None, None
    if not rows:
        return [], None
    out = []
    from datetime import time as dt_time
    for r in rows:
        try:
            dow = int(r.get("day_of_week"))
            if dow < 0 or dow > 6:
                return None, {"error": "day_of_week must be 0..6 (Mon..Sun)."}
            start_t = dt_time.fromisoformat(r.get("start_time", ""))
            end_t = dt_time.fromisoformat(r.get("end_time", ""))
        except (ValueError, TypeError):
            return None, {"error": "weekly_hours entry needs day_of_week (0..6), start_time HH:MM, end_time HH:MM."}
        if end_t <= start_t:
            return None, {"error": "end_time must be after start_time."}
        out.append({
            "day_of_week": dow,
            "start_time": start_t.isoformat(),
            "end_time": end_t.isoformat(),
        })
    return out, None


def _normalize_unavailable_dates(values: list | None) -> tuple[list | None, dict | None]:
    if values is None:
        return None, None
    if not values:
        return [], None
    seen = set()
    for v in values:
        try:
            date.fromisoformat(v)
        except (ValueError, TypeError):
            return None, {"error": f"Invalid date '{v}'. Use YYYY-MM-DD."}
        seen.add(v)
    return sorted(seen), None


async def handle_manage_volunteer(ctx: ToolContext, tool_input: dict) -> str:
    action = tool_input.get("action", "")

    if action == "list":
        query = select(Contact).where(Contact.tenant_id == ctx.tenant.id)
        phone = (tool_input.get("phone") or "").strip()
        name = (tool_input.get("name") or "").strip()
        if phone:
            query = query.where(Contact.phone.ilike(f"%{phone}%"))
        elif name:
            query = query.where(Contact.name.ilike(f"%{name}%"))
        result = await ctx.db.execute(query.order_by(Contact.name).limit(20))
        contacts = result.scalars().all()
        items = []
        for c in contacts:
            count_result = await ctx.db.execute(
                select(func.count()).select_from(Booking).where(
                    Booking.contact_id == c.id,
                    Booking.tenant_id == ctx.tenant.id,
                )
            )
            booking_count = count_result.scalar() or 0
            consent_result = await ctx.db.execute(
                select(ContactConsent).where(
                    ContactConsent.contact_id == c.id,
                    ContactConsent.tenant_id == ctx.tenant.id,
                )
            )
            consent = consent_result.scalar_one_or_none()
            items.append({
                "phone": c.phone,
                "name": c.name or "—",
                "email": c.email or "—",
                "status": c.status.value if c.status else "active",
                "consent": consent.status.value if consent else "unknown",
                "background_check_required": bool(c.background_check_required),
                "total_bookings": booking_count,
            })
        if not items:
            return json.dumps({"message": "No volunteers found."})
        return json.dumps({"volunteers": items})

    if action == "get":
        phone = (tool_input.get("phone") or "").strip()
        if not phone:
            return json.dumps({"error": "phone is required for 'get'."})
        result = await ctx.db.execute(
            select(Contact).where(
                Contact.phone == phone, Contact.tenant_id == ctx.tenant.id
            )
        )
        contact = result.scalar_one_or_none()
        if not contact:
            return json.dumps({"error": "Volunteer not found."})

        consent_result = await ctx.db.execute(
            select(ContactConsent).where(
                ContactConsent.contact_id == contact.id,
                ContactConsent.tenant_id == ctx.tenant.id,
            )
        )
        consent = consent_result.scalar_one_or_none()

        pref_result = await ctx.db.execute(
            select(ContactPreferredType.appointment_type_id, AppointmentType.name)
            .join(AppointmentType, AppointmentType.id == ContactPreferredType.appointment_type_id)
            .where(
                ContactPreferredType.contact_id == contact.id,
                ContactPreferredType.tenant_id == ctx.tenant.id,
            )
        )
        preferred = [r[1] for r in pref_result.all()]

        return json.dumps({
            "phone": contact.phone,
            "name": contact.name or "",
            "email": contact.email or "",
            "sex": contact.sex.value if contact.sex else None,
            "status": contact.status.value if contact.status else "active",
            "consent": consent.status.value if consent else "unknown",
            "background_check_required": bool(contact.background_check_required),
            "all_services_enabled": bool(contact.all_services_enabled),
            "preferred_services": preferred,
            "reminder_preference_days": contact.reminder_preference_days,
            "availability": contact.availability or [],
            "weekly_hours": contact.weekly_hours or [],
            "unavailable_dates": contact.unavailable_dates or [],
        })

    if action == "add":
        phone = (tool_input.get("phone") or "").strip()
        name = (tool_input.get("name") or "").strip()
        if not phone or not name:
            return json.dumps({"error": "phone and name are required for 'add'."})

        existing = await ctx.db.execute(
            select(Contact).where(
                Contact.phone == phone, Contact.tenant_id == ctx.tenant.id
            )
        )
        if existing.scalar_one_or_none():
            return json.dumps({"error": "A volunteer with that phone already exists."})

        type_ids, err = await _resolve_service_ids_by_name(
            ctx, tool_input.get("preferred_services") or []
        )
        if err:
            return json.dumps(err)

        weekly, err = _normalize_weekly_hours(tool_input.get("weekly_hours"))
        if err:
            return json.dumps(err)
        dates, err = _normalize_unavailable_dates(tool_input.get("unavailable_dates"))
        if err:
            return json.dumps(err)

        sex_val = tool_input.get("sex")
        try:
            sex_enum = (
                __import__("app.models.contact", fromlist=["ContactSex"]).ContactSex(sex_val)
                if sex_val else None
            )
        except ValueError:
            return json.dumps({"error": f"Invalid sex value '{sex_val}'."})

        contact = Contact(
            tenant_id=ctx.tenant.id,
            phone=phone,
            name=name,
            email=tool_input.get("email") or None,
            sex=sex_enum,
            all_services_enabled=bool(tool_input.get("all_services_enabled", False)),
            background_check_required=bool(
                tool_input.get("background_check_required", False)
            ),
            availability=tool_input.get("availability") or None,
            weekly_hours=weekly or None,
            unavailable_dates=dates or None,
            reminder_preference_days=tool_input.get("reminder_preference_days", 7),
        )
        ctx.db.add(contact)
        await ctx.db.flush()

        ctx.db.add(
            ContactConsent(
                tenant_id=ctx.tenant.id,
                contact_id=contact.id,
                contact_phone=phone,
                status=ConsentStatus.UNCONTACTED,
            )
        )

        if type_ids:
            await _sync_volunteer_services(ctx, contact.id, type_ids)

        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "phone": contact.phone,
            "name": contact.name,
        })

    if action == "update":
        phone = (tool_input.get("phone") or "").strip()
        if not phone:
            return json.dumps({"error": "phone is required for 'update'."})
        result = await ctx.db.execute(
            select(Contact).where(
                Contact.phone == phone, Contact.tenant_id == ctx.tenant.id
            )
        )
        contact = result.scalar_one_or_none()
        if not contact:
            return json.dumps({"error": "Volunteer not found."})

        if "name" in tool_input and tool_input["name"]:
            contact.name = tool_input["name"]
        if "email" in tool_input:
            contact.email = tool_input["email"] or None
        if "sex" in tool_input:
            try:
                contact.sex = (
                    __import__("app.models.contact", fromlist=["ContactSex"]).ContactSex(
                        tool_input["sex"]
                    )
                    if tool_input["sex"]
                    else None
                )
            except ValueError:
                return json.dumps({"error": f"Invalid sex value '{tool_input['sex']}'."})
        if "reminder_preference_days" in tool_input and tool_input["reminder_preference_days"] is not None:
            contact.reminder_preference_days = tool_input["reminder_preference_days"]
        if "background_check_required" in tool_input and tool_input["background_check_required"] is not None:
            contact.background_check_required = bool(tool_input["background_check_required"])
        if "all_services_enabled" in tool_input and tool_input["all_services_enabled"] is not None:
            contact.all_services_enabled = bool(tool_input["all_services_enabled"])
        if "availability" in tool_input:
            contact.availability = tool_input["availability"] or None
        if "weekly_hours" in tool_input:
            weekly, err = _normalize_weekly_hours(tool_input["weekly_hours"])
            if err:
                return json.dumps(err)
            contact.weekly_hours = weekly or None
        if "unavailable_dates" in tool_input:
            dates, err = _normalize_unavailable_dates(tool_input["unavailable_dates"])
            if err:
                return json.dumps(err)
            contact.unavailable_dates = dates or None
        if "preferred_services" in tool_input:
            type_ids, err = await _resolve_service_ids_by_name(
                ctx, tool_input["preferred_services"] or []
            )
            if err:
                return json.dumps(err)
            await _sync_volunteer_services(ctx, contact.id, type_ids)

        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "phone": contact.phone,
            "name": contact.name,
        })

    if action == "delete":
        phone = (tool_input.get("phone") or "").strip()
        if not phone:
            return json.dumps({"error": "phone is required for 'delete'."})
        result = await ctx.db.execute(
            select(Contact).where(
                Contact.phone == phone, Contact.tenant_id == ctx.tenant.id
            )
        )
        contact = result.scalar_one_or_none()
        if not contact:
            return json.dumps({"error": "Volunteer not found."})

        active_count = (await ctx.db.execute(
            select(func.count()).select_from(Booking).where(
                Booking.contact_id == contact.id,
                Booking.tenant_id == ctx.tenant.id,
                Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
            )
        )).scalar() or 0
        if active_count > 0:
            return json.dumps({
                "error": f"Cannot delete: {active_count} active booking(s). Cancel them first.",
            })

        await ctx.db.delete(contact)
        await ctx.db.flush()
        return json.dumps({"success": True, "deleted_phone": phone})

    return json.dumps({"error": f"Unknown action '{action}'. Use 'list', 'get', 'add', 'update', or 'delete'."})


async def handle_block_date(ctx: ToolContext, tool_input: dict) -> str:
    try:
        date_from = date.fromisoformat(tool_input["date_from"])
        date_to = date.fromisoformat(tool_input["date_to"])
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    if date_to < date_from:
        return json.dumps({"error": "End date must be on or after start date."})

    cancel_existing = tool_input.get("cancel_existing")

    # Check for existing bookings in the date range
    import zoneinfo
    tz = zoneinfo.ZoneInfo(ctx.tenant.business_timezone or "America/New_York")
    range_start = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=tz)
    range_end = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=tz)

    bookings_result = await ctx.db.execute(
        select(Booking).where(
            Booking.tenant_id == ctx.tenant.id,
            Booking.scheduled_at >= range_start,
            Booking.scheduled_at <= range_end,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )
    affected_bookings = bookings_result.scalars().all()

    # If there are bookings and admin hasn't decided yet, return the conflict
    if affected_bookings and cancel_existing is None:
        booking_list = []
        for b in affected_bookings:
            appt = await ctx.db.execute(
                select(AppointmentType).where(AppointmentType.id == b.appointment_type_id)
            )
            appt_type = appt.scalar_one_or_none()
            booking_list.append({
                "ref": _booking_ref(b.id),
                "customer_phone": b.contact_phone,
                "service": appt_type.name if appt_type else "Unknown",
                "date": b.scheduled_at.strftime("%A %B %d"),
                "time": b.scheduled_at.strftime("%I:%M %p"),
            })
        return json.dumps({
            "conflict": True,
            "affected_bookings": booking_list,
            "total_affected": len(booking_list),
            "message": f"There are {len(booking_list)} existing booking(s) in this date range. Ask the admin if they should be cancelled or kept as-is, then call block_date again with cancel_existing set to true or false.",
        })

    # Cancel affected bookings if requested
    cancelled_count = 0
    if affected_bookings and cancel_existing:
        for b in affected_bookings:
            b.status = BookingStatus.CANCELLED
            history = BookingHistory(
                booking_id=b.id,
                event_type=BookingEventType.STATUS_CHANGED,
                new_status=BookingStatus.CANCELLED,
                changed_by=ChangedBy.ADMIN,
                tenant_id=ctx.tenant.id,
            )
            ctx.db.add(history)
            try:
                await process_booking_cancellation(ctx.db, b, ctx.tenant, send_sms_notification=not ctx.test_mode)
            except Exception as e:
                logger.error("Failed to process cancellation for booking %s: %s", b.id, e)
            cancelled_count += 1

    # Create the blocked date
    blocked = BlockedDate(
        tenant_id=ctx.tenant.id,
        date_from=date_from,
        date_to=date_to,
        reason=tool_input.get("reason"),
    )
    ctx.db.add(blocked)
    await ctx.db.flush()

    result = {
        "success": True,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "reason": tool_input.get("reason", ""),
    }
    if cancelled_count > 0:
        result["cancelled_bookings"] = cancelled_count
    if affected_bookings and not cancel_existing:
        result["kept_bookings"] = len(affected_bookings)

    return json.dumps(result)


async def handle_unblock_date(ctx: ToolContext, tool_input: dict) -> str:
    try:
        date_from = date.fromisoformat(tool_input["date_from"])
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    result = await ctx.db.execute(
        select(BlockedDate).where(
            BlockedDate.tenant_id == ctx.tenant.id,
            BlockedDate.date_from == date_from,
        )
    )
    blocked = result.scalar_one_or_none()
    if not blocked:
        return json.dumps({"error": f"No date block found starting on {date_from}."})

    await ctx.db.delete(blocked)
    await ctx.db.flush()
    return json.dumps({"success": True, "message": f"Date block starting {date_from} has been removed."})


async def handle_cancel_event_bookings(ctx: ToolContext, tool_input: dict) -> str:
    """Cancel all active bookings on an event date and notify each volunteer.

    The event itself (specific-date slot or weekly window) is NOT touched —
    only the bookings against it. After cancellation each affected volunteer
    is sent a single SMS containing the reason (if any) and an invitation to
    sign up again. Two-phase: first call returns the preview, second call
    with ``confirm=true`` performs the work.
    """
    from app.services.sms import send_sms

    try:
        event_date = date.fromisoformat(tool_input["event_date"])
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid event_date. Use YYYY-MM-DD."})

    confirm = bool(tool_input.get("confirm"))
    reason = (tool_input.get("reason") or "").strip()
    rebook_message = (
        (tool_input.get("rebook_message") or "").strip()
        or "You can sign up again whenever you're ready — just text us back."
    )

    # Resolve service filter, if any.
    appt_filter_id = None
    appt_filter_name = None
    service_name = (tool_input.get("service_name") or "").strip()
    if service_name:
        appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, service_name)
        if not appt_type:
            return json.dumps({"error": f"Service '{service_name}' not found."})
        appt_filter_id = appt_type.id
        appt_filter_name = appt_type.name

    # Find every active booking on that date for this tenant.
    import zoneinfo
    tz = zoneinfo.ZoneInfo(ctx.tenant.business_timezone or "America/New_York")
    day_start = datetime.combine(event_date, datetime.min.time()).replace(tzinfo=tz)
    day_end = datetime.combine(event_date, datetime.max.time()).replace(tzinfo=tz)

    booking_query = select(Booking).where(
        Booking.tenant_id == ctx.tenant.id,
        Booking.scheduled_at >= day_start,
        Booking.scheduled_at <= day_end,
        Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
    )
    if appt_filter_id is not None:
        booking_query = booking_query.where(Booking.appointment_type_id == appt_filter_id)

    result = await ctx.db.execute(booking_query)
    bookings = list(result.scalars().all())

    if not bookings:
        scope = f" for '{appt_filter_name}'" if appt_filter_name else ""
        return json.dumps({
            "message": f"No active bookings on {event_date}{scope}. Nothing to cancel.",
        })

    # Hydrate appointment-type names in one query.
    type_ids = list({b.appointment_type_id for b in bookings})
    types_q = await ctx.db.execute(
        select(AppointmentType.id, AppointmentType.name).where(
            AppointmentType.id.in_(type_ids)
        )
    )
    name_by_type = {row.id: row.name for row in types_q.all()}

    # Preview phase — return the list and ask the admin to confirm.
    if not confirm:
        preview = [
            {
                "ref": _booking_ref(b.id),
                "service": name_by_type.get(b.appointment_type_id, "Unknown"),
                "volunteer_phone": b.contact_phone,
                "time": b.scheduled_at.strftime("%I:%M %p"),
            }
            for b in bookings
        ]
        scope = f" for '{appt_filter_name}'" if appt_filter_name else ""
        return json.dumps({
            "preview": True,
            "event_date": event_date.isoformat(),
            "service_filter": appt_filter_name,
            "total_to_cancel": len(preview),
            "bookings": preview,
            "message": (
                f"This will cancel {len(preview)} booking(s) on "
                f"{event_date.strftime('%A %B %d')}{scope} and SMS each volunteer. "
                f"Confirm to proceed."
            ),
        })

    # Execute phase.
    cancelled = 0
    notified = 0
    sms_failures = 0
    cancelled_phones: set[str] = set()
    notification_errors: list[str] = []
    preview_messages: list[dict] = []

    for booking in bookings:
        booking.status = BookingStatus.CANCELLED
        ctx.db.add(BookingHistory(
            booking_id=booking.id,
            event_type=BookingEventType.STATUS_CHANGED,
            new_status=BookingStatus.CANCELLED,
            changed_by=ChangedBy.ADMIN if ctx.is_admin else ChangedBy.USER_SMS,
            tenant_id=ctx.tenant.id,
            notes=f"Bulk cancellation: {reason}" if reason else "Bulk cancellation",
        ))
        cancelled += 1

        # Calendar deletion only — we'll send our own SMS with the bulk
        # context (reason + rebook invite) instead of the per-booking default.
        try:
            await process_booking_cancellation(
                ctx.db, booking, ctx.tenant, send_sms_notification=False
            )
        except Exception as e:
            logger.error("Calendar cleanup failed for booking %s: %s", booking.id, e)

        # One SMS (or preview) per affected volunteer — dedupe across
        # multi-service signups so a volunteer with three shifts on the same
        # day gets one notification, not three.
        if booking.contact_phone in cancelled_phones:
            continue
        cancelled_phones.add(booking.contact_phone)

        service_name_str = name_by_type.get(booking.appointment_type_id, "your shift")
        time_str = booking.scheduled_at.strftime("%A %B %d at %I:%M %p")
        reason_clause = f" ({reason})" if reason else ""
        sms_body = (
            f"Your booking for {service_name_str} on {time_str} has been "
            f"cancelled{reason_clause}. {rebook_message}"
        )

        if ctx.test_mode:
            # Surface what each volunteer would have received so the
            # Multi-Volunteer Test page can mirror it into the panels.
            preview_messages.append({"phone": booking.contact_phone, "body": sms_body})
            notified += 1
            continue

        try:
            await send_sms(
                to=booking.contact_phone,
                body=sms_body,
                tenant=ctx.tenant,
            )
            notified += 1
        except Exception as e:
            sms_failures += 1
            notification_errors.append(f"{booking.contact_phone}: {e}")
            logger.error("Failed to SMS %s: %s", booking.contact_phone, e)

    await ctx.db.flush()

    summary: dict = {
        "success": True,
        "event_date": event_date.isoformat(),
        "service_filter": appt_filter_name,
        "cancelled": cancelled,
        "volunteers_notified": notified,
        "unique_volunteers": len(cancelled_phones),
    }
    if sms_failures:
        summary["sms_failures"] = sms_failures
        summary["sms_errors"] = notification_errors[:5]  # cap noise
    if ctx.test_mode and preview_messages:
        summary["test_mode"] = True
        summary["preview_messages"] = preview_messages
    return json.dumps(summary)


async def handle_get_schedule(ctx: ToolContext, tool_input: dict) -> str:
    date_str = tool_input.get("date")
    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    # Get all bookings for the date
    result = await ctx.db.execute(
        select(Booking).where(
            Booking.tenant_id == ctx.tenant.id,
            func.date(Booking.scheduled_at) == target_date,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        ).order_by(Booking.scheduled_at)
    )
    bookings = result.scalars().all()

    booking_items = []
    for b in bookings:
        appt = await ctx.db.execute(
            select(AppointmentType).where(AppointmentType.id == b.appointment_type_id)
        )
        appt_type = appt.scalar_one_or_none()
        booking_items.append({
            "ref": _booking_ref(b.id),
            "time": b.scheduled_at.strftime("%I:%M %p"),
            "service": appt_type.name if appt_type else "Unknown",
            "customer_phone": b.contact_phone,
            "status": b.status.value,
        })

    # Get available slot count across services
    types_result = await ctx.db.execute(
        select(AppointmentType).where(
            AppointmentType.tenant_id == ctx.tenant.id,
            AppointmentType.is_active.is_(True),
        )
    )
    types = types_result.scalars().all()

    total_available = 0
    for appt_type in types:
        slots = await compute_available_slots(
            ctx.db, target_date, appt_type.id, ctx.tenant, max_slots=20
        )
        total_available += len(slots)

    return json.dumps({
        "date": target_date.strftime("%A %B %d"),
        "bookings": booking_items,
        "total_bookings": len(booking_items),
        "total_available_slots": total_available,
    })


async def handle_manage_service(ctx: ToolContext, tool_input: dict) -> str:
    action = tool_input.get("action", "")
    name = tool_input.get("name", "")

    if action == "create":
        duration = tool_input.get("duration_minutes")
        price = tool_input.get("price")
        if not duration or price is None:
            return json.dumps({"error": "duration_minutes and price are required for creating a service."})

        existing = await _resolve_appointment_type(ctx.db, ctx.tenant.id, name)
        if existing:
            return json.dumps({"error": f"Service '{name}' already exists."})

        appt_type = AppointmentType(
            tenant_id=ctx.tenant.id,
            name=name,
            duration_minutes=int(duration),
            price=float(price),
            description=tool_input.get("description"),
            is_active=True,
        )
        ctx.db.add(appt_type)
        await ctx.db.flush()

        return json.dumps({
            "success": True,
            "action": "created",
            "name": name,
            "duration_minutes": int(duration),
            "price": float(price),
        })

    elif action == "update":
        appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, name)
        if not appt_type:
            return json.dumps({"error": f"Service '{name}' not found."})

        if "duration_minutes" in tool_input:
            appt_type.duration_minutes = int(tool_input["duration_minutes"])
        if "price" in tool_input:
            appt_type.price = float(tool_input["price"])
        if "description" in tool_input:
            appt_type.description = tool_input["description"]

        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "action": "updated",
            "name": appt_type.name,
            "duration_minutes": appt_type.duration_minutes,
            "price": float(appt_type.price),
        })

    elif action == "deactivate":
        appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, name)
        if not appt_type:
            return json.dumps({"error": f"Service '{name}' not found."})

        appt_type.is_active = False
        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "action": "deactivated",
            "name": appt_type.name,
        })

    return json.dumps({"error": f"Unknown action '{action}'. Use: create, update, or deactivate."})


async def handle_send_announcement(ctx: ToolContext, tool_input: dict) -> str:
    message = tool_input.get("message", "").strip()
    if not message:
        return json.dumps({"error": "Message text is required."})

    service_name = tool_input.get("service_name")
    booking_date_str = tool_input.get("booking_date")
    status_filter = tool_input.get("status_filter")

    tenant_id = ctx.tenant.id

    # Build base query: active, opted-in contacts
    query = (
        select(Contact.id, Contact.phone)
        .join(ContactConsent, ContactConsent.contact_id == Contact.id)
        .where(
            Contact.tenant_id == tenant_id,
            Contact.status == ContactStatus.ACTIVE,
            ContactConsent.status == ConsentStatus.OPTED_IN,
            ContactConsent.tenant_id == tenant_id,
        )
    )

    # Resolve service name to appointment type ID if provided
    appt_type_id = None
    if service_name:
        appt_type = await _resolve_appointment_type(ctx.db, tenant_id, service_name)
        if not appt_type:
            return json.dumps({"error": f"Service '{service_name}' not found."})
        appt_type_id = appt_type.id

    # Build contact ID subqueries based on filters
    contact_filters = []

    if appt_type_id and not booking_date_str:
        # Contacts who prefer or have booked this service
        pref_sub = select(ContactPreferredType.contact_id).where(
            ContactPreferredType.tenant_id == tenant_id,
            ContactPreferredType.appointment_type_id == appt_type_id,
        )
        booking_sub = select(Booking.contact_id).where(
            Booking.tenant_id == tenant_id,
            Booking.appointment_type_id == appt_type_id,
        )
        contact_filters.append(Contact.id.in_(pref_sub.union(booking_sub)))

    if booking_date_str:
        try:
            booking_date = date.fromisoformat(booking_date_str)
        except ValueError:
            return json.dumps({"error": "Invalid booking_date format. Use YYYY-MM-DD."})

        # Contacts with bookings on the specified date
        date_booking_query = select(Booking.contact_id).where(
            Booking.tenant_id == tenant_id,
            func.date(Booking.scheduled_at) == booking_date,
        )

        # Apply status filter to the date query
        if status_filter == "upcoming":
            date_booking_query = date_booking_query.where(
                Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED])
            )
        elif status_filter == "past":
            date_booking_query = date_booking_query.where(
                Booking.status == BookingStatus.COMPLETED
            )
        elif status_filter == "cancelled":
            date_booking_query = date_booking_query.where(
                Booking.status == BookingStatus.CANCELLED
            )

        # Also filter by service if specified
        if appt_type_id:
            date_booking_query = date_booking_query.where(
                Booking.appointment_type_id == appt_type_id
            )

        contact_filters.append(Contact.id.in_(date_booking_query))

    elif status_filter and not booking_date_str:
        # Status filter without date — filter by booking status globally
        status_map = {
            "upcoming": [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED],
            "past": [BookingStatus.COMPLETED],
            "cancelled": [BookingStatus.CANCELLED],
        }
        statuses = status_map.get(status_filter)
        if statuses:
            status_sub = select(Booking.contact_id).where(
                Booking.tenant_id == tenant_id,
                Booking.status.in_(statuses),
            )
            if appt_type_id:
                status_sub = status_sub.where(Booking.appointment_type_id == appt_type_id)
            contact_filters.append(Contact.id.in_(status_sub))

    for f in contact_filters:
        query = query.where(f)

    result = await ctx.db.execute(query.distinct())
    recipients = result.all()
    phones = [r.phone for r in recipients]

    if not phones:
        return json.dumps({"message": "No recipients match the specified filters.", "total_recipients": 0})

    # Determine scope + build event_context when this is an event-specific send
    from app.models.announcement import RecipientScope
    from app.api.announcements import _render_announcement_message
    from app.prompts.conversation import get_announcement_header_template

    is_event_send = bool(booking_date_str and service_name)
    event_context: dict | None = None
    if is_event_send:
        event_context = {
            "event_label": service_name,
            "event_date": booking_date_str,
            "service_name": service_name,
            "appointment_type_id": str(appt_type_id) if appt_type_id else None,
        }

    # Build outgoing message: prepend rendered header for event sends.
    if event_context:
        template = await get_announcement_header_template(ctx.db, tenant_id)
        outgoing_message = _render_announcement_message(template, event_context, message)
    else:
        outgoing_message = message

    # Create announcement record
    announcement = Announcement(
        tenant_id=tenant_id,
        message=message,
        filter_appointment_type_ids=[str(appt_type_id)] if appt_type_id else None,
        status=AnnouncementStatus.SENDING,
        total_recipients=len(phones),
        event_context=event_context,
        recipient_scope=(
            RecipientScope.EVENT_SIGNUPS.value
            if is_event_send
            else RecipientScope.ALL.value
        ),
        created_by_admin_id=ctx.contact_id,
    )
    ctx.db.add(announcement)
    await ctx.db.flush()

    # Send SMS to each recipient (skip in test mode)
    sent = 0
    failed = 0
    if ctx.test_mode:
        sent = len(phones)
    else:
        for phone in phones:
            try:
                sms_result = await send_sms(phone, outgoing_message, ctx.tenant)
                if sms_result:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error("Failed to send announcement to %s: %s", phone, e)
                failed += 1

    # Update announcement record
    announcement.sent_count = sent
    announcement.failed_count = failed
    announcement.sent_at = datetime.now(timezone.utc)
    announcement.status = AnnouncementStatus.SENT if failed == 0 else AnnouncementStatus.FAILED
    await ctx.db.flush()

    # Build audience description
    audience_parts = []
    if service_name:
        audience_parts.append(f"service: {service_name}")
    if booking_date_str:
        audience_parts.append(f"bookings on: {booking_date_str}")
    if status_filter:
        audience_parts.append(f"status: {status_filter}")
    audience = ", ".join(audience_parts) if audience_parts else "all opted-in customers"

    response: dict = {
        "success": True,
        "total_recipients": len(phones),
        "sent": sent,
        "failed": failed,
        "audience": audience,
    }
    # In test mode, include the rendered body + recipient phones so the
    # Multi-Volunteer Test page can preview the announcement against each
    # selected volunteer instead of silently dropping it.
    if ctx.test_mode:
        response["test_mode"] = True
        response["preview_message"] = outgoing_message
        response["preview_recipients"] = list(phones)
    return json.dumps(response)


async def handle_suspend_customer(ctx: ToolContext, tool_input: dict) -> str:
    phone = tool_input.get("phone", "")
    reason = tool_input.get("reason", "")

    result = await ctx.db.execute(
        select(Contact).where(
            Contact.phone == phone,
            Contact.tenant_id == ctx.tenant.id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        return json.dumps({"error": f"No customer found with phone '{phone}'."})

    if contact.status == ContactStatus.SUSPENDED:
        return json.dumps({"error": f"Customer {phone} is already suspended."})
    if contact.status == ContactStatus.BANNED:
        return json.dumps({"error": f"Customer {phone} is banned."})

    from app.models.suspension import ContactSuspension, SuspensionType

    contact.status = ContactStatus.SUSPENDED

    suspension = ContactSuspension(
        tenant_id=ctx.tenant.id,
        contact_id=contact.id,
        contact_phone=phone,
        suspension_type=SuspensionType.MANUAL,
        reason=reason,
        notification_sent_at=datetime.now(timezone.utc),
    )
    ctx.db.add(suspension)
    await ctx.db.flush()

    return json.dumps({
        "success": True,
        "phone": phone,
        "reason": reason,
        "message": f"Customer {phone} has been suspended.",
    })


async def handle_unsuspend_customer(ctx: ToolContext, tool_input: dict) -> str:
    phone = tool_input.get("phone", "")

    result = await ctx.db.execute(
        select(Contact).where(
            Contact.phone == phone,
            Contact.tenant_id == ctx.tenant.id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        return json.dumps({"error": f"No customer found with phone '{phone}'."})

    if contact.status != ContactStatus.SUSPENDED:
        return json.dumps({"error": f"Customer {phone} is not suspended (status: {contact.status.value})."})

    contact.status = ContactStatus.ACTIVE

    # Restore consent if blocked
    consent_result = await ctx.db.execute(
        select(ContactConsent).where(
            ContactConsent.contact_id == contact.id,
            ContactConsent.tenant_id == ctx.tenant.id,
        )
    )
    consent = consent_result.scalar_one_or_none()
    if consent and consent.status == ConsentStatus.BLOCKED:
        consent.status = ConsentStatus.OPTED_IN
        consent.last_status_change_at = datetime.now(timezone.utc)

    await ctx.db.flush()

    return json.dumps({
        "success": True,
        "phone": phone,
        "message": f"Customer {phone} has been unsuspended and can book again.",
    })


async def _build_service_config(ctx: ToolContext, services_input: list | None):
    """Resolve service names to a JSONB-ready service_config list. Returns (config, error_dict_or_None)."""
    if services_input is None:
        return None, None
    if not services_input:
        return [], None
    config = []
    for svc in services_input:
        appt_type = await _resolve_appointment_type(
            ctx.db, ctx.tenant.id, svc.get("service_name", "")
        )
        if not appt_type:
            return None, {"error": f"Service '{svc.get('service_name')}' not found."}
        min_req = svc.get("min_required", 1)
        max_allow = svc.get("max_allowed", min_req)
        if min_req < 1:
            return None, {"error": f"min_required must be at least 1 for '{svc.get('service_name')}'."}
        if max_allow < min_req:
            return None, {"error": f"max_allowed ({max_allow}) must be >= min_required ({min_req}) for '{svc.get('service_name')}'."}
        config.append({
            "appointment_type_id": str(appt_type.id),
            "min_required": min_req,
            "max_allowed": max_allow,
        })
    return config, None


async def handle_manage_availability(ctx: ToolContext, tool_input: dict) -> str:
    from app.models.availability import AvailabilityRule

    action = tool_input.get("action", "")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if action == "list":
        rules_result = await ctx.db.execute(
            select(AvailabilityRule).where(
                AvailabilityRule.tenant_id == ctx.tenant.id,
                AvailabilityRule.is_active.is_(True),
            ).order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
        )
        rules = rules_result.scalars().all()
        items = []
        for r in rules:
            services = []
            if r.service_config:
                for cfg in r.service_config:
                    appt = await ctx.db.execute(
                        select(AppointmentType).where(AppointmentType.id == cfg.get("appointment_type_id"))
                    )
                    at = appt.scalar_one_or_none()
                    services.append({
                        "service": at.name if at else "Unknown",
                        "min_required": cfg.get("min_required", 1),
                        "max_allowed": cfg.get("max_allowed", 1),
                    })
            items.append({
                "id": str(r.id),
                "day": days[r.day_of_week],
                "label": r.label or "",
                "start": str(r.start_time)[:5],
                "end": str(r.end_time)[:5],
                "buffer_minutes": r.buffer_minutes,
                "services": services if services else "All services (min 1, max 1)",
            })
        if not items:
            return json.dumps({"message": "No availability rules configured."})
        return json.dumps({"rules": items})

    elif action == "set":
        day = tool_input.get("day_of_week")
        start = tool_input.get("start_time")
        end = tool_input.get("end_time")
        if day is None or not start or not end:
            return json.dumps({"error": "day_of_week, start_time, and end_time are required."})

        from datetime import time as dt_time
        try:
            start_time = dt_time.fromisoformat(start)
            end_time = dt_time.fromisoformat(end)
        except ValueError:
            return json.dumps({"error": "Invalid time format. Use HH:MM."})

        services_input = tool_input.get("services")
        svc_config, err = await _build_service_config(
            ctx, services_input if services_input else None
        )
        if err:
            return json.dumps(err)

        rule = AvailabilityRule(
            tenant_id=ctx.tenant.id,
            day_of_week=day,
            label=tool_input.get("label"),
            start_time=start_time,
            end_time=end_time,
            buffer_minutes=tool_input.get("buffer_minutes", 0),
            service_config=svc_config,
            is_active=True,
            allow_roster_sharing=bool(tool_input.get("allow_roster_sharing", True)),
        )
        ctx.db.add(rule)
        await ctx.db.flush()

        return json.dumps({
            "success": True,
            "id": str(rule.id),
            "day": days[day],
            "start": start,
            "end": end,
        })

    elif action in ("update", "delete"):
        rule_id = tool_input.get("id")
        if not rule_id:
            return json.dumps({"error": f"id is required for '{action}'."})
        try:
            rule_uuid = uuid.UUID(rule_id)
        except (ValueError, AttributeError):
            return json.dumps({"error": "Invalid id format."})
        rule_result = await ctx.db.execute(
            select(AvailabilityRule).where(
                AvailabilityRule.id == rule_uuid,
                AvailabilityRule.tenant_id == ctx.tenant.id,
            )
        )
        rule = rule_result.scalar_one_or_none()
        if not rule:
            return json.dumps({"error": "Availability rule not found."})

        if action == "delete":
            await ctx.db.delete(rule)
            await ctx.db.flush()
            return json.dumps({"success": True, "deleted_id": rule_id})

        # update — apply only fields present in input
        from datetime import time as dt_time
        if "day_of_week" in tool_input and tool_input["day_of_week"] is not None:
            rule.day_of_week = tool_input["day_of_week"]
        if "label" in tool_input:
            rule.label = tool_input["label"]
        if "start_time" in tool_input and tool_input["start_time"]:
            try:
                rule.start_time = dt_time.fromisoformat(tool_input["start_time"])
            except ValueError:
                return json.dumps({"error": "Invalid start_time. Use HH:MM."})
        if "end_time" in tool_input and tool_input["end_time"]:
            try:
                rule.end_time = dt_time.fromisoformat(tool_input["end_time"])
            except ValueError:
                return json.dumps({"error": "Invalid end_time. Use HH:MM."})
        if "buffer_minutes" in tool_input and tool_input["buffer_minutes"] is not None:
            rule.buffer_minutes = tool_input["buffer_minutes"]
        if "allow_roster_sharing" in tool_input and tool_input["allow_roster_sharing"] is not None:
            rule.allow_roster_sharing = bool(tool_input["allow_roster_sharing"])
        if "services" in tool_input:
            svc_config, err = await _build_service_config(ctx, tool_input["services"])
            if err:
                return json.dumps(err)
            rule.service_config = svc_config if svc_config else None
        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "id": str(rule.id),
            "day": days[rule.day_of_week],
            "start": str(rule.start_time)[:5],
            "end": str(rule.end_time)[:5],
        })

    return json.dumps({"error": f"Unknown action '{action}'. Use 'list', 'set', 'update', or 'delete'."})


async def handle_manage_specific_date_slot(ctx: ToolContext, tool_input: dict) -> str:
    from app.models.availability import AvailabilityRule, SpecificDateSlot
    from datetime import time as dt_time, timedelta as _timedelta

    action = tool_input.get("action", "")

    if action == "list":
        # Combined list: one-off events (SpecificDateSlot) within the
        # 4-week horizon + the NEXT occurrence of each active recurring
        # rule (AvailabilityRule). Each entry carries a volunteer
        # summary: total needed across services, total signed up, gap.
        today = date.today()
        horizon = today + _timedelta(days=28)

        # 1. One-off events
        one_off_q = await ctx.db.execute(
            select(SpecificDateSlot)
            .where(
                SpecificDateSlot.tenant_id == ctx.tenant.id,
                SpecificDateSlot.date >= today,
                SpecificDateSlot.date <= horizon,
                SpecificDateSlot.is_active.is_(True),
            )
            .order_by(SpecificDateSlot.date, SpecificDateSlot.start_time)
        )
        one_off_slots = list(one_off_q.scalars().all())

        # 2. Recurring rules — one entry each for the NEXT occurrence
        rules_q = await ctx.db.execute(
            select(AvailabilityRule)
            .where(
                AvailabilityRule.tenant_id == ctx.tenant.id,
                AvailabilityRule.is_active.is_(True),
            )
        )
        rules = list(rules_q.scalars().all())

        # 3. Resolve service names ONCE for all service_config entries
        all_service_ids: set[str] = set()
        for s in one_off_slots:
            for cfg in (s.service_config or []):
                sid = cfg.get("appointment_type_id")
                if sid:
                    all_service_ids.add(str(sid))
        for r in rules:
            for cfg in (r.service_config or []):
                sid = cfg.get("appointment_type_id")
                if sid:
                    all_service_ids.add(str(sid))
        service_names: dict[str, str] = {}
        if all_service_ids:
            n_q = await ctx.db.execute(
                select(AppointmentType.id, AppointmentType.name).where(
                    AppointmentType.id.in_(list(all_service_ids))
                )
            )
            service_names = {str(sid): name for sid, name in n_q.all()}

        # Helper: compute volunteer summary for a (date, service_config) pair.
        # Counts active bookings (SCHEDULED + RESCHEDULED) for the
        # services in service_config on that specific date.
        async def _summary_for(
            event_date: date, service_config: list[dict] | None
        ) -> dict:
            services: list[dict] = []
            total_needed = 0
            total_signed = 0
            if not service_config:
                return {
                    "services": "All services (min 1, max 1)",
                    "total_needed": 0,
                    "total_signed_up": 0,
                    "more_required": 0,
                }
            service_ids: list[str] = []
            for cfg in service_config:
                sid = cfg.get("appointment_type_id")
                if sid:
                    service_ids.append(str(sid))
            # Bulk-count signups per service for this date
            signups: dict[str, int] = {}
            if service_ids:
                from sqlalchemy import func as _func
                signup_q = await ctx.db.execute(
                    select(
                        Booking.appointment_type_id, _func.count(Booking.id)
                    )
                    .where(
                        Booking.tenant_id == ctx.tenant.id,
                        Booking.appointment_type_id.in_(service_ids),
                        _func.date(Booking.scheduled_at) == event_date,
                        Booking.status.in_(
                            [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
                        ),
                    )
                    .group_by(Booking.appointment_type_id)
                )
                for sid, cnt in signup_q.all():
                    signups[str(sid)] = int(cnt)
            for cfg in service_config:
                sid = cfg.get("appointment_type_id")
                sid_str = str(sid) if sid else None
                min_required = int(cfg.get("min_required", 1) or 0)
                max_allowed = cfg.get("max_allowed")
                signed = signups.get(sid_str, 0) if sid_str else 0
                gap = max(0, min_required - signed)
                services.append({
                    "service": service_names.get(sid_str, "Unknown") if sid_str else "Unknown",
                    "min_required": min_required,
                    "max_allowed": max_allowed,
                    "signed_up": signed,
                    "more_required": gap,
                })
                total_needed += min_required
                total_signed += signed
            return {
                "services": services,
                "total_needed": total_needed,
                "total_signed_up": total_signed,
                "more_required": max(0, total_needed - total_signed),
            }

        items: list[dict] = []

        # One-off entries
        for s in one_off_slots:
            summary = await _summary_for(s.date, s.service_config)
            items.append({
                "id": str(s.id),
                "kind": "one_off",
                "date": s.date.isoformat(),
                "label": s.label or "",
                "location": s.location or "",
                "start": str(s.start_time)[:5] if s.start_time else "",
                "end": str(s.end_time)[:5] if s.end_time else "",
                "buffer_minutes": s.buffer_minutes,
                **summary,
            })

        # Recurring entries — compute next occurrence per rule
        for r in rules:
            days_ahead = (r.day_of_week - today.weekday()) % 7
            next_date = today + _timedelta(days=days_ahead)
            if next_date > horizon:
                continue
            summary = await _summary_for(next_date, r.service_config)
            items.append({
                "id": str(r.id),
                "kind": "recurring",
                "date": next_date.isoformat(),
                "label": r.label or "",
                "location": r.location or "",
                "start": str(r.start_time)[:5] if r.start_time else "",
                "end": str(r.end_time)[:5] if r.end_time else "",
                "buffer_minutes": r.buffer_minutes,
                "recurrence": (
                    "weekly on " + ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][r.day_of_week]
                    if r.day_of_week is not None else "weekly"
                ),
                **summary,
            })

        # Sort all entries by next-occurrence date
        items.sort(key=lambda it: (it.get("date", ""), it.get("start", "")))

        if not items:
            return json.dumps({"message": "No upcoming events configured."})

        # next_action_hint nudges the LLM to follow up rather than
        # leaving the admin staring at a wall of text. Backstops the
        # admin system prompt rule (see prompt_admin_system).
        return json.dumps({
            "events": items,
            "horizon_days": 28,
            "summary": {
                "total_events": len(items),
                "one_off_count": sum(1 for it in items if it.get("kind") == "one_off"),
                "recurring_count": sum(1 for it in items if it.get("kind") == "recurring"),
            },
            "next_action_hint": (
                "Show the events to the admin grouped or listed by date. "
                "For EACH event include: label, date, time, location, and a "
                "one-line volunteer summary like '4 needed / 1 signed up / 3 more required'. "
                "After showing the list, ask if they want more details about "
                "any specific event (you can use get_schedule with the event "
                "date for the deeper view, or recruitment_status for an "
                "active campaign's progress)."
            ),
        })

    if action == "add":
        date_str = tool_input.get("date", "")
        start = tool_input.get("start_time", "")
        end = tool_input.get("end_time", "")
        if not date_str or not start or not end:
            return json.dumps({"error": "date, start_time, and end_time are required for 'add'."})
        try:
            slot_date = date.fromisoformat(date_str)
            start_time = dt_time.fromisoformat(start)
            end_time = dt_time.fromisoformat(end)
        except ValueError:
            return json.dumps({"error": "Invalid date or time format."})

        services_input = tool_input.get("services")
        svc_config, err = await _build_service_config(
            ctx, services_input if services_input else None
        )
        if err:
            return json.dumps(err)

        slot = SpecificDateSlot(
            tenant_id=ctx.tenant.id,
            date=slot_date,
            label=tool_input.get("label"),
            location=tool_input.get("location"),
            description=tool_input.get("description"),
            start_time=start_time,
            end_time=end_time,
            buffer_minutes=tool_input.get("buffer_minutes", 0),
            service_config=svc_config,
            is_active=True,
            allow_roster_sharing=bool(tool_input.get("allow_roster_sharing", True)),
        )
        ctx.db.add(slot)
        await ctx.db.flush()
        return json.dumps({
            "success": True,
            "id": str(slot.id),
            "date": date_str,
            "start": start,
            "end": end,
            "label": tool_input.get("label", ""),
        })

    if action in ("update", "delete"):
        slot_id = tool_input.get("id")
        if not slot_id:
            return json.dumps({"error": f"id is required for '{action}'."})
        try:
            slot_uuid = uuid.UUID(slot_id)
        except (ValueError, AttributeError):
            return json.dumps({"error": "Invalid id format."})
        slot_result = await ctx.db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.id == slot_uuid,
                SpecificDateSlot.tenant_id == ctx.tenant.id,
            )
        )
        slot = slot_result.scalar_one_or_none()
        if not slot:
            return json.dumps({"error": "Event not found."})

        if action == "delete":
            await ctx.db.delete(slot)
            await ctx.db.flush()
            return json.dumps({"success": True, "deleted_id": slot_id})

        if "date" in tool_input and tool_input["date"]:
            try:
                slot.date = date.fromisoformat(tool_input["date"])
            except ValueError:
                return json.dumps({"error": "Invalid date. Use YYYY-MM-DD."})
        if "start_time" in tool_input and tool_input["start_time"]:
            try:
                slot.start_time = dt_time.fromisoformat(tool_input["start_time"])
            except ValueError:
                return json.dumps({"error": "Invalid start_time. Use HH:MM."})
        if "end_time" in tool_input and tool_input["end_time"]:
            try:
                slot.end_time = dt_time.fromisoformat(tool_input["end_time"])
            except ValueError:
                return json.dumps({"error": "Invalid end_time. Use HH:MM."})
        if "label" in tool_input:
            slot.label = tool_input["label"]
        if "location" in tool_input:
            slot.location = tool_input["location"]
        if "description" in tool_input:
            slot.description = tool_input["description"]
        if "buffer_minutes" in tool_input and tool_input["buffer_minutes"] is not None:
            slot.buffer_minutes = tool_input["buffer_minutes"]
        if "allow_roster_sharing" in tool_input and tool_input["allow_roster_sharing"] is not None:
            slot.allow_roster_sharing = bool(tool_input["allow_roster_sharing"])
        service_config_changed = False
        if "services" in tool_input:
            svc_config, err = await _build_service_config(ctx, tool_input["services"])
            if err:
                return json.dumps(err)
            slot.service_config = svc_config if svc_config else None
            service_config_changed = True
        await ctx.db.flush()

        if service_config_changed:
            from app.agents.recruiter import executor as recruiter_executor
            synced = await recruiter_executor.sync_campaign_goals_from_slot(
                ctx.db, slot
            )
        else:
            synced = 0

        return json.dumps({
            "success": True,
            "id": str(slot.id),
            "date": slot.date.isoformat(),
            "start": str(slot.start_time)[:5],
            "end": str(slot.end_time)[:5],
            **({"campaigns_synced": synced} if synced else {}),
        })

    return json.dumps({"error": f"Unknown action '{action}'. Use 'list', 'add', 'update', or 'delete'."})


# ── Handler registry ──

from app.agents.recruiter.chat_tools import (
    handle_approve_recruitment_campaign,
    handle_delete_recruitment_campaign,
    handle_recruitment_status,
    handle_start_recruitment_campaign,
)

TOOL_HANDLERS = {
    "list_services": handle_list_services,
    "check_availability": handle_check_availability,
    "get_event_roster": handle_get_event_roster,
    "get_my_appointments": handle_get_my_appointments,
    "book_appointment": handle_book_appointment,
    "cancel_appointment": handle_cancel_appointment,
    "reschedule_appointment": handle_reschedule_appointment,
    "search_bookings": handle_search_bookings,
    "manage_volunteer": handle_manage_volunteer,
    "block_date": handle_block_date,
    "unblock_date": handle_unblock_date,
    "cancel_event_bookings": handle_cancel_event_bookings,
    "get_schedule": handle_get_schedule,
    "manage_service": handle_manage_service,
    "manage_availability": handle_manage_availability,
    "manage_specific_date_slot": handle_manage_specific_date_slot,
    "send_announcement": handle_send_announcement,
    "suspend_customer": handle_suspend_customer,
    "unsuspend_customer": handle_unsuspend_customer,
    "start_recruitment_campaign": handle_start_recruitment_campaign,
    "approve_recruitment_campaign": handle_approve_recruitment_campaign,
    "recruitment_status": handle_recruitment_status,
    "delete_recruitment_campaign": handle_delete_recruitment_campaign,
}
