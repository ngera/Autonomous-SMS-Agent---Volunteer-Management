"""APScheduler cron jobs for background processing.

Five daily jobs:
- reminder_dispatch (08:00): evaluate customers and send qualifying reminders
- follow_up_dispatch (10:00): follow up on reminders with no response after 48hrs
- strike_decay (00:00): mark strikes >30 days old as decayed
- conversation_expiry (02:00): expire conversations with no activity for 7 days
- announcement_dispatch (every hour): send scheduled announcements whose time has arrived

Multi-tenant: reminder and follow-up jobs iterate over all active tenants,
checking each tenant's local time before dispatching.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.announcement import Announcement, AnnouncementStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.contact_preferred_type import ContactPreferredType
from app.models.conversation import Conversation, ConversationStatus
from app.models.pattern import CustomerAppointmentPattern
from app.models.reminder import Reminder, ReminderStatus
from app.models.strike import ContactStrike
from app.models.suspension import ContactSuspension, ReviewDecision
from app.models.tenant import Tenant
from app.services.sms import send_sms

logger = get_logger("scheduler")


# ── Event-lifecycle scheduler jobs (Phase 1 steps 5c + 8) ──────────


async def prune_stale_candidates_tick() -> None:
    """Daily job — two-pass DELETE on volunteer_candidate (decision #29c + #32).

    Pass 1 — stale 'new' rows: status='new' AND last_seen_at < NOW() - 30d
      AND invited_at IS NULL AND dismissed_at IS NULL.
      The trailing predicates are race-safe per decision #29(c).

    Pass 2 — terminal-state retention cap (1 year by default per #32):
      status='dismissed' AND dismissed_at < NOW() - 365d, OR
      status='invited' AND invited_at < NOW() - 365d.
    """
    from app.models.system_setting import SystemSetting

    async with async_session_factory() as db:
        try:
            # Resolve per-tenant overrides (default 30 / 365).
            # For simplicity we run with global defaults — tenants can
            # override via system_settings rows that the next iteration
            # of this job will read.
            prune_days = 30
            terminal_days = 365

            sql_pass1 = """
                DELETE FROM volunteer_candidate
                WHERE status = 'new'
                  AND last_seen_at < NOW() - (:prune_days || ' days')::INTERVAL
                  AND invited_at IS NULL
                  AND dismissed_at IS NULL;
            """
            sql_pass2 = """
                DELETE FROM volunteer_candidate
                WHERE (status = 'dismissed' AND dismissed_at < NOW() - (:terminal_days || ' days')::INTERVAL)
                   OR (status = 'invited'   AND invited_at   < NOW() - (:terminal_days || ' days')::INTERVAL);
            """
            from sqlalchemy import text
            r1 = await db.execute(text(sql_pass1), {"prune_days": prune_days})
            r2 = await db.execute(text(sql_pass2), {"terminal_days": terminal_days})
            await db.commit()
            logger.info(
                "candidate prune: pass1 deleted=%d pass2 deleted=%d",
                r1.rowcount or 0, r2.rowcount or 0,
            )
        except Exception:
            await db.rollback()
            logger.exception("prune_stale_candidates_tick failed")


async def event_status_ping_tick() -> None:
    """Phase 2 — Roster status auto-pings dispatcher (decision #9).

    Runs every minute. Walks active tenants → slots in live window →
    checks each of the 7 scheduled offsets (T-30/-15/0/+15/+30/+45/+60)
    against the current minute. Dispatches via SMS + in-app to all
    eligible admins. Idempotent against double-fire via UNIQUE
    constraint on (slot, admin, scheduled_for, channel).
    """
    from app.services.event_status_ping import (
        event_status_ping_tick as _tick,
    )
    async with async_session_factory() as db:
        try:
            count = await _tick(db)
            if count:
                logger.info("event_status_ping_tick dispatched %d pings", count)
        except Exception:
            await db.rollback()
            logger.exception("event_status_ping_tick failed")


async def no_show_review_tick() -> None:
    """Phase 4 — at T+start+30min, auto-create no_show reviews for any
    booking whose slot started ≥30 min ago and has no check-in.

    Idempotent via the UNIQUE(booking_id) constraint on booking_review.
    Runs every 5 minutes; that's fine-grained enough that the 'T+30min'
    boundary lands within a few ticks for any given slot.
    """
    from app.models.availability import SpecificDateSlot
    from app.models.booking import Booking, BookingStatus
    from app.services.booking_review import (
        create_no_show_review_for_booking,
    )

    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    eastern = ZoneInfo("America/New_York")
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            from sqlalchemy import select

            today = now_utc.date()
            slot_result = await db.execute(
                select(Booking, SpecificDateSlot)
                .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
                .where(
                    Booking.status != BookingStatus.CANCELLED,
                    Booking.checked_in_at.is_(None),
                    SpecificDateSlot.date.between(
                        today - timedelta(days=2), today + timedelta(days=1)
                    ),
                )
            )
            created = 0
            for booking, slot in slot_result.all():
                start_at = datetime.combine(slot.date, slot.start_time).replace(
                    tzinfo=eastern
                )
                if (now_utc - start_at) < timedelta(minutes=30):
                    continue
                review = await create_no_show_review_for_booking(
                    db, booking=booking
                )
                if review is not None:
                    created += 1
            await db.commit()
            if created:
                logger.info(
                    "no_show_review_tick: created %d no_show reviews", created
                )
        except Exception:
            await db.rollback()
            logger.exception("no_show_review_tick failed")


async def pending_review_tick() -> None:
    """Phase 4 — at T+end + review_grace_minutes (tenant SystemSetting,
    default 120), create pending reviews for any booking that has a
    check-in but no review yet.

    Runs every 15 minutes. Per-tenant grace window is read inside.
    """
    from sqlalchemy import select
    from app.models.availability import SpecificDateSlot
    from app.models.booking import Booking, BookingStatus
    from app.models.system_setting import SystemSetting
    from app.models.tenant import Tenant
    from app.services.booking_review import (
        DEFAULT_REVIEW_GRACE_MINUTES,
        create_pending_review_for_booking,
    )

    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    eastern = ZoneInfo("America/New_York")
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            today = now_utc.date()
            slot_result = await db.execute(
                select(Booking, SpecificDateSlot, Tenant)
                .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
                .join(Tenant, Booking.tenant_id == Tenant.id)
                .where(
                    Booking.status != BookingStatus.CANCELLED,
                    Booking.checked_in_at.is_not(None),
                    SpecificDateSlot.date.between(
                        today - timedelta(days=3), today + timedelta(days=1)
                    ),
                )
            )

            # Per-tenant grace cache (avoids one SystemSetting lookup per booking)
            tenant_grace_cache: dict = {}

            async def _grace_for(tenant_id) -> int:
                if tenant_id in tenant_grace_cache:
                    return tenant_grace_cache[tenant_id]
                row = (
                    await db.execute(
                        select(SystemSetting).where(
                            SystemSetting.tenant_id == tenant_id,
                            SystemSetting.key == "review_grace_minutes",
                        )
                    )
                ).scalar_one_or_none()
                try:
                    value = (
                        int(row.value) if row is not None else DEFAULT_REVIEW_GRACE_MINUTES
                    )
                except (TypeError, ValueError):
                    value = DEFAULT_REVIEW_GRACE_MINUTES
                tenant_grace_cache[tenant_id] = value
                return value

            created = 0
            for booking, slot, _tenant in slot_result.all():
                grace_min = await _grace_for(booking.tenant_id)
                end_at = datetime.combine(slot.date, slot.end_time).replace(
                    tzinfo=eastern
                )
                if (now_utc - end_at) < timedelta(minutes=grace_min):
                    continue
                review = await create_pending_review_for_booking(
                    db, booking=booking, slot=slot
                )
                if review is not None:
                    created += 1
            await db.commit()
            if created:
                logger.info(
                    "pending_review_tick: created %d pending reviews", created
                )
        except Exception:
            await db.rollback()
            logger.exception("pending_review_tick failed")


async def auto_close_forgotten_checkouts_tick() -> None:
    """Run every 15 minutes — finds bookings checked in but not out
    where T+end+1h has passed; sets checked_out_at=end_at,
    checked_out_source='auto_close' (decision #13).

    Implementation: join bookings → specific_date_slots, compute
    slot end_at + 1h in tenant's Eastern timezone, compare to NOW().
    """
    from app.models.availability import SpecificDateSlot
    from app.models.booking import Booking, BookingStatus, CHECKOUT_SOURCE_AUTO_CLOSE

    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    eastern = ZoneInfo("America/New_York")
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            # Get candidate bookings: checked in, not checked out, slot
            # ended ≥ 1h ago. Coarse date filter at SQL; refine in Python.
            from sqlalchemy import select
            cutoff_date = (now_utc - timedelta(days=1)).date()
            result = await db.execute(
                select(Booking, SpecificDateSlot)
                .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
                .where(
                    Booking.checked_in_at.is_not(None),
                    Booking.checked_out_at.is_(None),
                    Booking.status != BookingStatus.CANCELLED,
                    SpecificDateSlot.date >= cutoff_date,
                )
            )
            count = 0
            for booking, slot in result.all():
                end_at = datetime.combine(slot.date, slot.end_time).replace(tzinfo=eastern)
                if (now_utc - end_at) < timedelta(hours=1):
                    continue
                booking.checked_out_at = end_at
                booking.checked_out_source = CHECKOUT_SOURCE_AUTO_CLOSE
                count += 1
            await db.commit()
            if count:
                logger.info("auto_close_forgotten_checkouts: closed %d bookings", count)
        except Exception:
            await db.rollback()
            logger.exception("auto_close_forgotten_checkouts_tick failed")


async def reminder_dispatch() -> None:
    """Daily — evaluate customers per tenant and send qualifying reminders.

    Iterates over all active tenants. For each tenant, finds patterns
    with upcoming due dates and sends reminders to qualifying customers.
    """
    async with async_session_factory() as db:
        try:
            # Get all active tenants
            tenants_result = await db.execute(
                select(Tenant).where(Tenant.is_active.is_(True))
            )
            tenants = tenants_result.scalars().all()

            for tenant in tenants:
                try:
                    await _reminder_dispatch_for_tenant(db, tenant)
                except Exception as e:
                    logger.error(
                        "Reminder dispatch failed for tenant %s: %s",
                        tenant.slug, str(e), exc_info=True,
                    )

            await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error("Reminder dispatch failed: %s", str(e), exc_info=True)


async def _reminder_dispatch_for_tenant(db, tenant: Tenant) -> None:
    """Send qualifying reminders for a single tenant."""
    today = date.today()
    lookahead = today + timedelta(days=3)

    # Find patterns with upcoming due dates for this tenant
    result = await db.execute(
        select(CustomerAppointmentPattern).where(
            CustomerAppointmentPattern.tenant_id == tenant.id,
            CustomerAppointmentPattern.next_due_date != None,  # noqa: E711
            CustomerAppointmentPattern.next_due_date <= lookahead,
        )
    )
    patterns = result.scalars().all()

    sent_count = 0
    skipped_count = 0

    for pattern in patterns:
        phone = pattern.contact_phone
        type_id = pattern.appointment_type_id

        # Check for active suspension
        suspension = await db.execute(
            select(ContactSuspension).where(
                ContactSuspension.contact_phone == phone,
                ContactSuspension.tenant_id == tenant.id,
                ContactSuspension.lifted_at == None,  # noqa: E711
                ContactSuspension.review_decision != ReviewDecision.LIFTED,
            )
        )
        if suspension.scalar_one_or_none():
            skipped_count += 1
            continue

        # Check consent
        consent_result = await db.execute(
            select(ContactConsent).where(
                ContactConsent.contact_phone == phone,
                ContactConsent.tenant_id == tenant.id,
            )
        )
        consent = consent_result.scalar_one_or_none()
        if not consent or consent.status != ConsentStatus.OPTED_IN:
            skipped_count += 1
            continue

        # Check no existing pending/sent reminder for this type
        existing = await db.execute(
            select(Reminder).where(
                Reminder.contact_phone == phone,
                Reminder.tenant_id == tenant.id,
                Reminder.appointment_type_id == type_id,
                Reminder.status.in_([
                    ReminderStatus.PENDING,
                    ReminderStatus.SENT,
                ]),
            )
        )
        if existing.scalar_one_or_none():
            skipped_count += 1
            continue

        # Create reminder
        reminder = Reminder(
            contact_phone=phone,
            contact_id=pattern.contact_id,
            tenant_id=tenant.id,
            appointment_type_id=type_id,
            scheduled_for=pattern.next_due_date,
            status=ReminderStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            pattern_snapshot={
                "blended_interval_days": float(pattern.blended_interval_days or 0),
                "confidence": pattern.confidence.value if pattern.confidence else "default",
                "completed_count": pattern.completed_booking_count,
            },
        )
        db.add(reminder)

        # Send SMS
        interval_days = int(pattern.blended_interval_days or 28)
        await send_sms(
            to=phone,
            body=(
                f"Hi! It's been about {interval_days} days since your last appointment. "
                f"Would you like to book your next session? "
                f"Reply YES to start booking or STOP to opt out of reminders."
            ),
            tenant=tenant,
        )
        sent_count += 1

    logger.info(
        "Reminder dispatch for tenant %s: %d sent, %d skipped",
        tenant.slug, sent_count, skipped_count,
    )


async def follow_up_dispatch() -> None:
    """Daily — follow up on reminders with no response after 48hrs.

    Iterates over all active tenants.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    async with async_session_factory() as db:
        try:
            tenants_result = await db.execute(
                select(Tenant).where(Tenant.is_active.is_(True))
            )
            tenants = tenants_result.scalars().all()

            for tenant in tenants:
                try:
                    await _follow_up_for_tenant(db, tenant, cutoff)
                except Exception as e:
                    logger.error(
                        "Follow-up dispatch failed for tenant %s: %s",
                        tenant.slug, str(e), exc_info=True,
                    )

            await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error("Follow-up dispatch failed: %s", str(e), exc_info=True)


async def _follow_up_for_tenant(db, tenant: Tenant, cutoff: datetime) -> None:
    """Send follow-up messages for a single tenant."""
    result = await db.execute(
        select(Reminder).where(
            Reminder.tenant_id == tenant.id,
            Reminder.status == ReminderStatus.SENT,
            Reminder.sent_at != None,  # noqa: E711
            Reminder.sent_at <= cutoff,
            Reminder.follow_up_sent_at == None,  # noqa: E711
        )
    )
    reminders = result.scalars().all()

    sent_count = 0
    for reminder in reminders:
        await send_sms(
            to=reminder.contact_phone,
            body=(
                "Just a gentle follow-up — would you like to book your "
                "next appointment? Reply YES to book or STOP to opt out."
            ),
            tenant=tenant,
        )
        reminder.follow_up_sent_at = datetime.now(timezone.utc)
        sent_count += 1

    # Mark reminders that still have no response after follow-up
    follow_up_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    await db.execute(
        update(Reminder)
        .where(
            Reminder.tenant_id == tenant.id,
            Reminder.status == ReminderStatus.SENT,
            Reminder.follow_up_sent_at != None,  # noqa: E711
            Reminder.follow_up_sent_at <= follow_up_cutoff,
        )
        .values(status=ReminderStatus.NO_RESPONSE)
    )

    if sent_count:
        logger.info("Follow-up for tenant %s: %d sent", tenant.slug, sent_count)


async def strike_decay() -> None:
    """Daily 00:00 — mark strikes >30 days old as decayed.

    Strikes older than 30 days no longer count toward the 4-strike suspension
    threshold. This runs globally (not per-tenant) since it's a simple timestamp update.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                update(ContactStrike)
                .where(
                    ContactStrike.created_at <= cutoff,
                    ContactStrike.decayed_at == None,  # noqa: E711
                )
                .values(decayed_at=datetime.now(timezone.utc))
                .returning(ContactStrike.id)
            )
            decayed_ids = result.scalars().all()

            await db.commit()
            logger.info("Strike decay complete: %d strikes decayed", len(decayed_ids))

        except Exception as e:
            await db.rollback()
            logger.error("Strike decay failed: %s", str(e), exc_info=True)


async def conversation_expiry() -> None:
    """Daily 02:00 — expire conversations with no activity for 7 days.

    Runs globally (not per-tenant) since it's a simple timestamp-based update.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                update(Conversation)
                .where(
                    Conversation.status == ConversationStatus.ACTIVE,
                    Conversation.last_message_at <= cutoff,
                )
                .values(status=ConversationStatus.EXPIRED)
                .returning(Conversation.id)
            )
            expired_ids = result.scalars().all()

            await db.commit()
            logger.info(
                "Conversation expiry complete: %d conversations expired",
                len(expired_ids),
            )

        except Exception as e:
            await db.rollback()
            logger.error("Conversation expiry failed: %s", str(e), exc_info=True)


async def announcement_dispatch() -> None:
    """Hourly — send scheduled announcements whose scheduled_at has passed."""
    from app.api.announcements import _get_recipient_phones, _send_announcement

    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Announcement).where(
                    Announcement.status == AnnouncementStatus.SCHEDULED,
                    Announcement.scheduled_at <= now,
                )
            )
            announcements = result.scalars().all()

            for ann in announcements:
                try:
                    await _send_announcement(str(ann.id), str(ann.tenant_id))
                    logger.info("Sent scheduled announcement %s", ann.id)
                except Exception as e:
                    logger.error(
                        "Failed to send announcement %s: %s",
                        ann.id, str(e), exc_info=True,
                    )

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("Announcement dispatch failed: %s", str(e), exc_info=True)


async def recruitment_daily_report() -> None:
    """Once daily — write the per-campaign progress SMS to admin's phone."""
    from app.agents.recruiter.reporter import daily_report_run
    try:
        await daily_report_run()
    except Exception as e:  # noqa: BLE001
        logger.error("recruitment_daily_report failed: %s", e, exc_info=True)


async def recruitment_tick() -> None:
    """Every 15 min — drive active recruitment campaigns.

    For each active tenant, load active campaigns sorted by event date ASC
    (locked decision #5 — closest event first). For each, ask
    scheduler_engine for the next action and dispatch via executor.
    """
    from app.agents.recruiter import executor, scheduler_engine
    from app.models.availability import SpecificDateSlot
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
        RecruitmentWave,
    )

    async with async_session_factory() as db:
        try:
            tenants_result = await db.execute(
                select(Tenant).where(Tenant.is_active.is_(True))
            )
            tenants = tenants_result.scalars().all()

            for tenant in tenants:
                try:
                    await _recruitment_tick_for_tenant(db, tenant)
                except Exception as e:
                    logger.error(
                        "Recruitment tick failed for tenant %s: %s",
                        tenant.slug, str(e), exc_info=True,
                    )

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("Recruitment tick failed: %s", str(e), exc_info=True)


async def _recruitment_tick_for_tenant(db, tenant: Tenant) -> None:
    from app.agents.recruiter import executor, scheduler_engine
    from app.models.availability import SpecificDateSlot
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
        RecruitmentWave,
    )

    # Pull ACTIVE campaigns joined to their event slots; order by event
    # date ASC so the closest-event-first ordering is intrinsic.
    rows_q = await db.execute(
        select(RecruitmentCampaign, SpecificDateSlot)
        .join(
            SpecificDateSlot,
            SpecificDateSlot.id == RecruitmentCampaign.event_slot_id,
        )
        .where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status == CampaignStatus.ACTIVE,
        )
        .order_by(SpecificDateSlot.date.asc())
    )
    rows = list(rows_q.all())
    if not rows:
        return

    # Pre-compute the per-campaign fill snapshot so we can derive the
    # tenant-wide min-phase service set in one pass. A service is in
    # min-phase if ANY active campaign has signups < min_required for it.
    from datetime import datetime as _dt
    snapshots: list[tuple] = []  # (campaign, slot, fill, event_dt, waves)
    min_phase_service_ids: set[str] = set()
    for campaign, slot in rows:
        waves_q = await db.execute(
            select(RecruitmentWave).where(
                RecruitmentWave.campaign_id == campaign.id
            )
        )
        waves = list(waves_q.scalars().all())
        service_ids = [
            uuid.UUID(g["appointment_type_id"])
            for g in campaign.goals or []
            if g.get("appointment_type_id")
        ]
        fill = scheduler_engine.FillSnapshot(
            per_service=await executor.current_signups_per_service(
                db, slot, service_ids
            )
        )
        # Min-phase contribution from this campaign
        for goal in campaign.goals or []:
            sid = goal.get("appointment_type_id")
            if not sid:
                continue
            min_req = (
                goal.get("min_required")
                if goal.get("min_required") is not None
                else goal.get("min_acceptable")
                if goal.get("min_acceptable") is not None
                else goal.get("target", 0)
            )
            try:
                min_int = int(min_req or 0)
            except (TypeError, ValueError):
                min_int = 0
            current = fill.per_service.get(str(sid), 0)
            if current < min_int:
                min_phase_service_ids.add(str(sid))

        # Combine slot.date + slot.start_time IN TENANT-LOCAL TIME
        # and convert to UTC for comparison with `now`. Earlier this
        # was stamping local time as tzinfo=UTC, which silently moved
        # the event up to the tenant's UTC offset earlier — and made
        # the scheduler decide the event had already "passed" hours
        # before its real start, triggering ABANDON on future events.
        import pytz
        try:
            local_tz = pytz.timezone(tenant.business_timezone or "UTC")
        except Exception:
            local_tz = pytz.UTC
        naive_local = _dt.combine(
            slot.date, slot.start_time or _dt.min.time()
        )
        event_dt = local_tz.localize(naive_local).astimezone(timezone.utc)
        snapshots.append((campaign, slot, fill, event_dt, waves))

    fired = 0
    completed = 0
    for campaign, slot, fill, event_dt, waves in snapshots:
        action = scheduler_engine.next_action(
            campaign,
            waves,
            fill,
            event_dt,
            min_phase_service_ids=min_phase_service_ids,
        )

        if action.kind == scheduler_engine.ActionKind.SEND_WAVE and action.wave_id:
            wave = next((w for w in waves if w.id == action.wave_id), None)
            if wave:
                try:
                    await executor.execute_send_wave(
                        db, tenant, campaign, wave, slot, phase=action.phase
                    )
                    fired += 1
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "Failed to send wave %s for campaign %s: %s",
                        wave.id, campaign.id, e,
                    )
        elif action.kind == scheduler_engine.ActionKind.COMPLETE:
            await executor.mark_campaign_completed(db, campaign, action.reason)
            completed += 1
        elif action.kind == scheduler_engine.ActionKind.ABANDON:
            # ABANDON = event passed without meeting min staffing →
            # FAILED, not COMPLETED. The earlier code mis-routed this
            # through mark_campaign_completed, parading failed musters
            # as completions and silently cancelling every wave.
            await executor.mark_campaign_failed(
                db, campaign, action.reason
            )
            completed += 1
        elif action.kind == scheduler_engine.ActionKind.ESCALATE:
            await executor.mark_campaign_paused(db, campaign, action.reason)
            try:
                await _send_escalation_alert(db, tenant, campaign, slot, action.reason)
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "Failed to send escalation alert for campaign %s: %s",
                    campaign.id, e,
                )

    if fired or completed:
        logger.info(
            "Recruitment tick tenant %s: %d waves fired, %d completed",
            tenant.slug, fired, completed,
        )


async def _send_escalation_alert(
    db, tenant, campaign, slot, reason: str
) -> None:
    """SMS the campaign's creating admin when the agent has to pause.

    Mirrors the message into the admin's test-conversation history so the
    admin can see the alert next to the rest of the recruitment exchange.
    """
    from app.agents.recruiter import executor as recruiter_executor
    from app.models.admin_user import AdminUser
    from app.services.sms import send_sms

    admin = await db.get(AdminUser, campaign.created_by_admin_id)
    if not admin or not admin.phone:
        return
    body = (
        f"Recruitment paused for {slot.label or 'event'} on "
        f"{slot.date.isoformat()}: {reason} "
        "Open the dashboard to review and resume."
    )
    try:
        ok = await send_sms(admin.phone, body, tenant)
    except Exception:
        ok = False
    if ok:
        try:
            await recruiter_executor._append_to_admin_conversation(
                db, tenant.id, admin.phone, body
            )
        except Exception:
            logger.exception(
                "Failed to mirror escalation alert into admin conversation"
            )


# ── KPI summary digest ───────────────────────────────────────────────
#
# Daily SMS digest of the dashboard's KPI numbers. Per-tenant
# configurable in system_settings:
#   - kpi_summary_sms_enabled        : "true" / "false"
#   - kpi_summary_sms_time           : "HH:MM" in tenant timezone
#   - kpi_summary_sms_days_of_week   : CSV of 0..6 (0=Mon..6=Sun)
#   - last_kpi_summary_sent_date     : YYYY-MM-DD idempotency stamp
#
# The tick fires every 5 minutes and uses the idempotency stamp +
# local-time gate to ensure exactly one digest goes out per
# configured day, even if APScheduler is delayed.


async def kpi_summary_tick() -> None:
    """Every 5 min — fan out the daily KPI digest to admins of each
    tenant whose configured time has arrived. See
    [services/kpi_summary.py](backend/app/services/kpi_summary.py)
    for what's in the digest body."""
    import pytz

    from app.models.admin_user import AdminRole, AdminUser
    from app.models.system_setting import SystemSetting
    from app.services.kpi_summary import (
        compute_kpi_summary,
        format_kpi_summary_sms,
    )

    async with async_session_factory() as db:
        try:
            tenants = (await db.execute(
                select(Tenant).where(Tenant.is_active.is_(True))
            )).scalars().all()
            now_utc = datetime.now(timezone.utc)

            for tenant in tenants:
                try:
                    await _kpi_summary_for_tenant(
                        db, tenant, now_utc,
                        AdminRole=AdminRole, AdminUser=AdminUser,
                        SystemSetting=SystemSetting,
                        compute_kpi_summary=compute_kpi_summary,
                        format_kpi_summary_sms=format_kpi_summary_sms,
                        pytz=pytz,
                    )
                except Exception as e:
                    logger.error(
                        "KPI summary tick failed for tenant %s: %s",
                        tenant.slug, str(e), exc_info=True,
                    )
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("KPI summary tick failed: %s", str(e), exc_info=True)


async def _kpi_summary_for_tenant(
    db,
    tenant: Tenant,
    now_utc: datetime,
    *,
    AdminRole,
    AdminUser,
    SystemSetting,
    compute_kpi_summary,
    format_kpi_summary_sms,
    pytz,
) -> None:
    """Send the daily digest for one tenant if today is a configured
    day, the local scheduled time has arrived, and we haven't already
    sent today."""
    settings_rows = (await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key.in_([
                "kpi_summary_sms_enabled",
                "kpi_summary_sms_time",
                "kpi_summary_sms_days_of_week",
                "last_kpi_summary_sent_date",
            ]),
        )
    )).scalars().all()
    s: dict[str, str] = {r.key: r.value for r in settings_rows}

    if (s.get("kpi_summary_sms_enabled") or "false").lower() != "true":
        return

    # Parse schedule. Bad/missing values are conservative no-ops.
    time_str = s.get("kpi_summary_sms_time") or "08:00"
    try:
        sched_h, sched_m = (int(x) for x in time_str.split(":")[:2])
    except (ValueError, TypeError):
        logger.warning(
            "tenant %s has invalid kpi_summary_sms_time=%r; skipping",
            tenant.slug, time_str,
        )
        return

    dow_csv = s.get("kpi_summary_sms_days_of_week") or "0,1,2,3,4,5,6"
    try:
        allowed_dows = {int(x.strip()) for x in dow_csv.split(",") if x.strip()}
    except ValueError:
        logger.warning(
            "tenant %s has invalid kpi_summary_sms_days_of_week=%r; skipping",
            tenant.slug, dow_csv,
        )
        return

    tz = pytz.timezone(tenant.business_timezone or "UTC")
    local_now = now_utc.astimezone(tz)
    if local_now.weekday() not in allowed_dows:
        return

    # Idempotency: did we already fire today (tenant-local date)?
    today_str = local_now.date().isoformat()
    if s.get("last_kpi_summary_sent_date") == today_str:
        return

    # The local time gate: send when we've passed the scheduled time.
    # Using >= rather than == makes the job tolerant of APScheduler
    # delays — we'll catch up on the next tick after the configured
    # time has passed.
    scheduled_today = local_now.replace(
        hour=sched_h, minute=sched_m, second=0, microsecond=0
    )
    if local_now < scheduled_today:
        return

    # Lookup recipients — active OWNER + MANAGER admins with a phone.
    recipients = (await db.execute(
        select(AdminUser).where(
            AdminUser.tenant_id == tenant.id,
            AdminUser.is_active.is_(True),
            AdminUser.role.in_([AdminRole.OWNER, AdminRole.MANAGER]),
            AdminUser.phone.is_not(None),
        )
    )).scalars().all()
    recipients = [a for a in recipients if (a.phone or "").strip()]
    if not recipients:
        logger.info(
            "tenant %s KPI digest scheduled but no admin recipients", tenant.slug,
        )
        # Still stamp so we don't retry every tick — admins must configure
        # at least one recipient phone for digests to land.
        await _stamp_last_sent(db, tenant.id, today_str, SystemSetting)
        return

    summary = await compute_kpi_summary(db, tenant)
    body = format_kpi_summary_sms(summary)

    sent_to = 0
    for admin in recipients:
        try:
            ok = await send_sms(admin.phone, body, tenant)
            if ok:
                sent_to += 1
        except Exception:
            logger.exception(
                "tenant %s — failed to send KPI digest to %s",
                tenant.slug, admin.phone,
            )

    await _stamp_last_sent(db, tenant.id, today_str, SystemSetting)
    logger.info(
        "tenant %s KPI digest sent to %d/%d admins",
        tenant.slug, sent_to, len(recipients),
    )


async def _stamp_last_sent(
    db, tenant_id: uuid.UUID, today_str: str, SystemSetting,
) -> None:
    """Upsert last_kpi_summary_sent_date so the next tick today bails."""
    existing = (await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == "last_kpi_summary_sent_date",
        )
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = today_str
        existing.updated_at = now
    else:
        db.add(SystemSetting(
            tenant_id=tenant_id,
            key="last_kpi_summary_sent_date",
            value=today_str,
        ))
    await db.flush()
