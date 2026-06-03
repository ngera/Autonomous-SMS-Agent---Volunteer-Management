"""Phase 2 — Roster status auto-pings dispatcher.

Decisions:
  - #9: 7 ping times per slot (T-30, T-15, T, T+15, T+30, T+45, T+60).
  - #18: pings dispatched to all admins in receiving roles (OWNER +
    MANAGER); per-event coordinator deferred to backlog.
  - Suppression rule: when everyone is checked in, the current ping
    is replaced by a single "All checked in ✓" and remaining T+* pings
    for that slot get pre-inserted as skipped_reason='event_full_checked_in'.
  - Idempotency: a UNIQUE constraint on
    (slot_id, admin_user_id, scheduled_for, channel) makes the dispatcher
    safe against double-fire (e.g. two scheduler ticks racing).

Run order each tick (called by event_status_ping_tick in jobs.py):
  1. Walk active tenants.
  2. For each tenant, find slots whose start_at_utc places any of the
     7 ping offsets within the last 60s window.
  3. For each due (slot, offset) pair, dispatch to every eligible admin
     by SMS + in-app notification, recording rows in roster_status_ping_log.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

import pytz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.notification import AdminNotification, NotificationType
from app.models.roster_status_ping_log import (
    PING_CHANNEL_IN_APP,
    PING_CHANNEL_SMS,
    PING_SKIPPED_DISPATCH_FAILED,
    PING_SKIPPED_EVENT_FULL,
    RosterStatusPingLog,
)
from app.models.tenant import Tenant
from app.services.sms import send_sms

logger = get_logger("event_status_ping")


# 7 ping offsets in minutes from slot.start_at_utc.
PING_OFFSETS_MINUTES: tuple[int, ...] = (-30, -15, 0, 15, 30, 45, 60)

# Channels to dispatch per ping. SMS + in-app for Phase 2; email is
# wired in the table but not dispatched yet (waits for a Resend
# notification stack).
PHASE2_CHANNELS: tuple[str, ...] = (PING_CHANNEL_SMS, PING_CHANNEL_IN_APP)


def _slot_start_utc(slot: SpecificDateSlot, tz_name: str) -> datetime:
    """Compose the slot's start_at as a UTC datetime."""
    tz = pytz.timezone(tz_name or "America/New_York")
    local_dt = tz.localize(datetime.combine(slot.date, slot.start_time))
    return local_dt.astimezone(timezone.utc)


def _missing_names_capped(
    bookings_with_contacts: Sequence[tuple[Booking, Contact]],
    cap: int = 4,
) -> tuple[str, int]:
    """Return (`Jane D., Bob R., +2 more`, missing_count)."""
    missing = [
        (b, c)
        for b, c in bookings_with_contacts
        if b.checked_in_at is None
    ]
    if not missing:
        return ("", 0)
    names = []
    for _, c in missing[:cap]:
        if not c.name:
            continue
        # Use "First L." short form.
        parts = c.name.split()
        first = parts[0] if parts else ""
        last_initial = (parts[1][0] + ".") if len(parts) > 1 else ""
        names.append(f"{first} {last_initial}".strip())
    overflow = len(missing) - len(names)
    listing = ", ".join(names)
    if overflow > 0:
        listing = f"{listing}, +{overflow} more" if listing else f"{overflow} not yet checked in"
    return (listing or f"{len(missing)} not yet checked in", len(missing))


async def _eligible_admins(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[AdminUser]:
    """Recipients for pings: OWNER + MANAGER, active, not opted out."""
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.tenant_id == tenant_id,
            AdminUser.is_active.is_(True),
            AdminUser.role.in_([AdminRole.OWNER, AdminRole.MANAGER]),
            AdminUser.status_pings_opted_out.is_(False),
        )
    )
    return list(result.scalars().all())


async def _bookings_for_slot(
    db: AsyncSession, slot_id: uuid.UUID
) -> list[tuple[Booking, Contact]]:
    result = await db.execute(
        select(Booking, Contact)
        .join(Contact, Booking.contact_id == Contact.id)
        .where(
            Booking.event_slot_id == slot_id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    return list(result.all())


def _matches_offset(
    slot_start_utc: datetime, now_minute: datetime, offset_min: int
) -> bool:
    """Was the scheduled ping at slot_start_utc + offset_min in the
    last minute (between now_minute and now_minute + 1 min)?"""
    scheduled = slot_start_utc + timedelta(minutes=offset_min)
    # Truncate scheduled to minute.
    scheduled_minute = scheduled.replace(second=0, microsecond=0)
    return scheduled_minute == now_minute


async def _render_ping_body(
    db: AsyncSession,
    *,
    slot: SpecificDateSlot,
    bookings_with_contacts: Sequence[tuple[Booking, Contact]],
    tenant_id: uuid.UUID,
    all_in: bool,
) -> str:
    """Render the SMS body for a single ping."""
    from app.prompts.conversation import _get_prompt, PROMPT_KEYS

    if all_in:
        tpl = await _get_prompt(
            db,
            "prompt_roster_status_all_in",
            PROMPT_KEYS["prompt_roster_status_all_in"],
            tenant_id,
        )
        return tpl.format(event_name=slot.label or "(unnamed event)")

    tpl = await _get_prompt(
        db,
        "prompt_roster_status_ping",
        PROMPT_KEYS["prompt_roster_status_ping"],
        tenant_id,
    )
    total = len(bookings_with_contacts)
    checked_in = sum(
        1 for b, _ in bookings_with_contacts if b.checked_in_at is not None
    )
    missing_str, _ = _missing_names_capped(bookings_with_contacts, cap=4)
    return tpl.format(
        event_name=slot.label or "(unnamed event)",
        checked_in_count=checked_in,
        total_count=total,
        missing_names_capped=missing_str,
        link=f"/run-sheet/{slot.id}",
    )


async def _record_ping(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    slot_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    scheduled_for: datetime,
    channel: str,
    sent_at: datetime | None,
    skipped_reason: str | None,
) -> bool:
    """Insert a roster_status_ping_log row. Returns True if inserted,
    False on UNIQUE conflict (duplicate skipped silently).
    """
    stmt = (
        pg_insert(RosterStatusPingLog.__table__)
        .values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            slot_id=slot_id,
            admin_user_id=admin_user_id,
            scheduled_for=scheduled_for,
            sent_at=sent_at,
            skipped_reason=skipped_reason,
            channel=channel,
        )
        .on_conflict_do_nothing(
            constraint="uq_ping_per_recipient_per_time",
        )
    )
    result = await db.execute(stmt)
    return (result.rowcount or 0) > 0


async def _mark_suppression(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    slot_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    current_scheduled_for: datetime,
    slot_start_utc: datetime,
) -> None:
    """When suppression fires (all checked in), pre-insert log rows for
    all REMAINING T+* pings (offsets > current) with
    skipped_reason='event_full_checked_in'. The T+60 ping is always
    allowed through so admin gets the post-event review pointer.
    """
    # Compute scheduled UTC datetimes for remaining offsets > the current
    # one, excluding T+60 which still goes out.
    current_offset_min = round(
        (current_scheduled_for - slot_start_utc).total_seconds() / 60
    )
    for offset in PING_OFFSETS_MINUTES:
        if offset <= current_offset_min:
            continue
        if offset == 60:
            continue
        sched = slot_start_utc + timedelta(minutes=offset)
        for channel in PHASE2_CHANNELS:
            await _record_ping(
                db,
                tenant_id=tenant_id,
                slot_id=slot_id,
                admin_user_id=admin_user_id,
                scheduled_for=sched,
                channel=channel,
                sent_at=None,
                skipped_reason=PING_SKIPPED_EVENT_FULL,
            )


async def _dispatch_ping_to_admin(
    db: AsyncSession,
    *,
    tenant: Tenant,
    slot: SpecificDateSlot,
    admin: AdminUser,
    bookings_with_contacts: Sequence[tuple[Booking, Contact]],
    scheduled_for: datetime,
    body: str,
    all_in: bool,
    slot_start_utc: datetime,
) -> None:
    """Try to dispatch one ping to one admin across SMS + in-app channels.

    Idempotency: if a row already exists for
    (slot, admin, scheduled_for, channel), the upsert no-ops and we
    silently skip that channel.
    """
    # SMS channel
    if admin.phone:
        inserted = await _record_ping(
            db,
            tenant_id=tenant.id,
            slot_id=slot.id,
            admin_user_id=admin.id,
            scheduled_for=scheduled_for,
            channel=PING_CHANNEL_SMS,
            sent_at=None,  # Filled in on successful send below.
            skipped_reason=None,
        )
        if inserted:
            try:
                await send_sms(to=admin.phone, body=body, tenant=tenant)
                # Update sent_at on the row we just inserted.
                # (Simpler: update directly via raw SQL keyed on the same tuple.)
                from sqlalchemy import update
                await db.execute(
                    update(RosterStatusPingLog)
                    .where(
                        RosterStatusPingLog.slot_id == slot.id,
                        RosterStatusPingLog.admin_user_id == admin.id,
                        RosterStatusPingLog.scheduled_for == scheduled_for,
                        RosterStatusPingLog.channel == PING_CHANNEL_SMS,
                    )
                    .values(sent_at=datetime.now(timezone.utc))
                )
            except Exception:
                logger.exception(
                    "Failed to send status ping SMS for slot=%s admin=%s",
                    slot.id, admin.id,
                )
                from sqlalchemy import update
                await db.execute(
                    update(RosterStatusPingLog)
                    .where(
                        RosterStatusPingLog.slot_id == slot.id,
                        RosterStatusPingLog.admin_user_id == admin.id,
                        RosterStatusPingLog.scheduled_for == scheduled_for,
                        RosterStatusPingLog.channel == PING_CHANNEL_SMS,
                    )
                    .values(skipped_reason=PING_SKIPPED_DISPATCH_FAILED)
                )

    # In-app channel — always attempted (regardless of phone).
    inserted_in_app = await _record_ping(
        db,
        tenant_id=tenant.id,
        slot_id=slot.id,
        admin_user_id=admin.id,
        scheduled_for=scheduled_for,
        channel=PING_CHANNEL_IN_APP,
        sent_at=datetime.now(timezone.utc),
        skipped_reason=None,
    )
    if inserted_in_app:
        # Append AdminNotification so the bell icon picks it up.
        db.add(
            AdminNotification(
                tenant_id=tenant.id,
                admin_user_id=admin.id,
                type=NotificationType.ROSTER_STATUS_PING,
                title=f"Roster status: {slot.label or 'event'}",
                body=body,
                reference_id=slot.id,
                reference_type="specific_date_slots",
            )
        )

    # Suppression rule: if all in AND this isn't the T+60 final, pre-insert
    # rows for remaining T+* offsets so they don't fire on the next tick.
    if all_in:
        await _mark_suppression(
            db,
            tenant_id=tenant.id,
            slot_id=slot.id,
            admin_user_id=admin.id,
            current_scheduled_for=scheduled_for,
            slot_start_utc=slot_start_utc,
        )


async def event_status_ping_tick(db: AsyncSession) -> int:
    """Single tick of the auto-ping scheduler.

    Returns the number of (admin, slot, ping_time) dispatches attempted.
    Scheduler wrapper in jobs.py opens the AsyncSession and handles
    commit/rollback.
    """
    now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    dispatched = 0

    # Active tenants — for Phase 2 we send to every active tenant whose
    # pings aren't opted-out at the tenant level. (Per-tenant
    # status_pings_enabled SystemSetting honored below.)
    tenants_result = await db.execute(
        select(Tenant).where(Tenant.is_active.is_(True))
    )
    tenants = list(tenants_result.scalars().all())

    for tenant in tenants:
        # Per-tenant enable check (defaults to TRUE).
        if not await _tenant_pings_enabled(db, tenant.id):
            continue

        # Get slots in a 90-minute window around NOW (covers all 7 offsets).
        today = date.today()
        slots_result = await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == tenant.id,
                SpecificDateSlot.is_active.is_(True),
                SpecificDateSlot.date.between(
                    today - timedelta(days=1), today + timedelta(days=1)
                ),
            )
        )
        slots = list(slots_result.scalars().all())

        if not slots:
            continue

        admins = await _eligible_admins(db, tenant.id)
        if not admins:
            continue

        for slot in slots:
            slot_start_utc = _slot_start_utc(slot, tenant.business_timezone)
            # Which offset (if any) is due this minute?
            due_offset = None
            for offset in PING_OFFSETS_MINUTES:
                if _matches_offset(slot_start_utc, now_minute, offset):
                    due_offset = offset
                    break
            if due_offset is None:
                continue

            scheduled_for = slot_start_utc + timedelta(minutes=due_offset)
            bookings_with_contacts = await _bookings_for_slot(db, slot.id)
            total = len(bookings_with_contacts)
            checked_in = sum(
                1
                for b, _ in bookings_with_contacts
                if b.checked_in_at is not None
            )
            all_in = total > 0 and checked_in == total

            body = await _render_ping_body(
                db,
                slot=slot,
                bookings_with_contacts=bookings_with_contacts,
                tenant_id=tenant.id,
                all_in=all_in,
            )

            for admin in admins:
                try:
                    await _dispatch_ping_to_admin(
                        db,
                        tenant=tenant,
                        slot=slot,
                        admin=admin,
                        bookings_with_contacts=bookings_with_contacts,
                        scheduled_for=scheduled_for,
                        body=body,
                        all_in=all_in,
                        slot_start_utc=slot_start_utc,
                    )
                    dispatched += 1
                except IntegrityError:
                    # Race with another tick; safe to ignore.
                    await db.rollback()
                except Exception:
                    logger.exception(
                        "Ping dispatch failed slot=%s admin=%s",
                        slot.id, admin.id,
                    )

    await db.commit()
    return dispatched


async def _tenant_pings_enabled(
    db: AsyncSession, tenant_id: uuid.UUID
) -> bool:
    """Read SystemSetting `status_pings_enabled` (default TRUE)."""
    from app.models.system_setting import SystemSetting

    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == "status_pings_enabled",
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return True
    val = (row.value or "").strip().lower()
    return val not in ("false", "0", "off", "no")


# ── STOP STATUS / STOP STATUS ALL handlers ──────────────────────────


async def silence_admin_for_slot(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    slot_id: uuid.UUID,
) -> int:
    """Pre-insert roster_status_ping_log rows for all upcoming pings
    (>= NOW) for a single (admin, slot) so the dispatcher skips them.

    Returns the count of rows actually inserted (some may already exist).
    """
    result = await db.execute(
        select(SpecificDateSlot).where(SpecificDateSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        return 0
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one()
    slot_start_utc = _slot_start_utc(slot, tenant.business_timezone)
    now = datetime.now(timezone.utc)
    inserted = 0
    for offset in PING_OFFSETS_MINUTES:
        sched = slot_start_utc + timedelta(minutes=offset)
        if sched < now:
            continue
        for channel in PHASE2_CHANNELS:
            ok = await _record_ping(
                db,
                tenant_id=tenant_id,
                slot_id=slot_id,
                admin_user_id=admin_user_id,
                scheduled_for=sched,
                channel=channel,
                sent_at=None,
                skipped_reason="admin_silenced",
            )
            if ok:
                inserted += 1
    await db.flush()
    return inserted


async def silence_admin_globally(
    db: AsyncSession, *, admin_user_id: uuid.UUID
) -> None:
    """Set admin_users.status_pings_opted_out=TRUE."""
    from sqlalchemy import update
    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == admin_user_id)
        .values(status_pings_opted_out=True)
    )
    await db.flush()
