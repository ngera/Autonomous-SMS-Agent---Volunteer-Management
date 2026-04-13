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
    types = result.scalars().all()
    items = [
        {
            "name": t.name,
            "duration_minutes": t.duration_minutes,
            "price": float(t.price),
            "description": t.description or "",
        }
        for t in types
    ]
    return json.dumps({"services": items})


async def handle_check_availability(ctx: ToolContext, tool_input: dict) -> str:
    try:
        target_date = date.fromisoformat(tool_input["date"])
    except (ValueError, KeyError):
        return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})

    service_name = tool_input.get("service_name")

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
                "spots_remaining": remaining,
            }
            if needs_more > 0:
                slot_info["needs_more_to_confirm"] = needs_more
            all_slots.append(slot_info)

    if not all_slots:
        return json.dumps({"message": f"No available slots on {target_date.strftime('%A %B %d')}."})

    return json.dumps({"date": tool_input["date"], "slots": all_slots})


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
    service_name = tool_input.get("service_name", "")
    date_str = tool_input.get("date", "")
    time_str = tool_input.get("time", "")

    appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, service_name)
    if not appt_type:
        return json.dumps({"error": f"Service '{service_name}' not found."})

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

    # Create booking
    booking = Booking(
        tenant_id=ctx.tenant.id,
        contact_id=ctx.contact_id,
        contact_phone=ctx.contact_phone,
        appointment_type_id=appt_type.id,
        scheduled_at=scheduled_at,
        price_at_booking=float(appt_type.price),
        status=BookingStatus.SCHEDULED,
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

    # Process calendar + ICS (no SMS — Claude's response is the confirmation)
    try:
        await process_booking_creation(ctx.db, booking, ctx.tenant, send_sms_notification=False)
    except Exception as e:
        logger.error("process_booking_creation failed (booking still saved): %s", e)

    ctx.booking_created = True

    base_url = f"https://{ctx.tenant.api_domain}/api/v1/calendar/{booking.id}"

    return json.dumps({
        "success": True,
        "ref": _booking_ref(booking.id),
        "service": appt_type.name,
        "date": scheduled_at.strftime("%A %B %d"),
        "time": scheduled_at.strftime("%I:%M %p"),
        "price": float(appt_type.price),
        "calendar_link": f"{base_url}/new.ics",
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
        event_type=BookingEventType.STATUS_CHANGE,
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
                event_type=BookingEventType.STATUS_CHANGE,
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

    # Create announcement record
    announcement = Announcement(
        tenant_id=tenant_id,
        message=message,
        filter_appointment_type_ids=[str(appt_type_id)] if appt_type_id else None,
        status=AnnouncementStatus.SENDING,
        total_recipients=len(phones),
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
                sms_result = await send_sms(phone, message, ctx.tenant)
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

    return json.dumps({
        "success": True,
        "total_recipients": len(phones),
        "sent": sent,
        "failed": failed,
        "audience": audience,
    })


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

        # Build service_config
        svc_config = None
        services_input = tool_input.get("services")
        if services_input:
            svc_config = []
            for svc in services_input:
                appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, svc.get("service_name", ""))
                if not appt_type:
                    return json.dumps({"error": f"Service '{svc.get('service_name')}' not found."})
                min_req = svc.get("min_required", 1)
                max_allow = svc.get("max_allowed", min_req)
                if min_req < 1:
                    return json.dumps({"error": f"min_required must be at least 1 for '{svc.get('service_name')}'."})
                if max_allow < min_req:
                    return json.dumps({"error": f"max_allowed ({max_allow}) must be >= min_required ({min_req}) for '{svc.get('service_name')}'."})
                svc_config.append({
                    "appointment_type_id": str(appt_type.id),
                    "min_required": min_req,
                    "max_allowed": max_allow,
                })

        rule = AvailabilityRule(
            tenant_id=ctx.tenant.id,
            day_of_week=day,
            label=tool_input.get("label"),
            start_time=start_time,
            end_time=end_time,
            buffer_minutes=tool_input.get("buffer_minutes", 0),
            service_config=svc_config,
            is_active=True,
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

    return json.dumps({"error": f"Unknown action '{action}'. Use 'list' or 'set'."})


async def handle_add_specific_date_slot(ctx: ToolContext, tool_input: dict) -> str:
    from app.models.availability import SpecificDateSlot

    date_str = tool_input.get("date", "")
    start = tool_input.get("start_time", "")
    end = tool_input.get("end_time", "")

    if not date_str or not start or not end:
        return json.dumps({"error": "date, start_time, and end_time are required."})

    from datetime import time as dt_time
    try:
        slot_date = date.fromisoformat(date_str)
        start_time = dt_time.fromisoformat(start)
        end_time = dt_time.fromisoformat(end)
    except ValueError:
        return json.dumps({"error": "Invalid date or time format."})

    # Build service_config
    svc_config = None
    services_input = tool_input.get("services")
    if services_input:
        svc_config = []
        for svc in services_input:
            appt_type = await _resolve_appointment_type(ctx.db, ctx.tenant.id, svc.get("service_name", ""))
            if not appt_type:
                return json.dumps({"error": f"Service '{svc.get('service_name')}' not found."})
            svc_config.append({
                "appointment_type_id": str(appt_type.id),
                "min_required": svc.get("min_required", 1),
                "max_allowed": svc.get("max_allowed", svc.get("min_required", 1)),
            })

    slot = SpecificDateSlot(
        tenant_id=ctx.tenant.id,
        date=slot_date,
        label=tool_input.get("label"),
        start_time=start_time,
        end_time=end_time,
        buffer_minutes=tool_input.get("buffer_minutes", 0),
        service_config=svc_config,
        is_active=True,
    )
    ctx.db.add(slot)
    await ctx.db.flush()

    return json.dumps({
        "success": True,
        "date": date_str,
        "start": start,
        "end": end,
        "label": tool_input.get("label", ""),
    })


# ── Handler registry ──

TOOL_HANDLERS = {
    "list_services": handle_list_services,
    "check_availability": handle_check_availability,
    "get_my_appointments": handle_get_my_appointments,
    "book_appointment": handle_book_appointment,
    "cancel_appointment": handle_cancel_appointment,
    "reschedule_appointment": handle_reschedule_appointment,
    "search_bookings": handle_search_bookings,
    "lookup_customer": handle_lookup_customer,
    "block_date": handle_block_date,
    "unblock_date": handle_unblock_date,
    "get_schedule": handle_get_schedule,
    "manage_service": handle_manage_service,
    "manage_availability": handle_manage_availability,
    "add_specific_date_slot": handle_add_specific_date_slot,
    "send_announcement": handle_send_announcement,
    "suspend_customer": handle_suspend_customer,
    "unsuspend_customer": handle_unsuspend_customer,
}
