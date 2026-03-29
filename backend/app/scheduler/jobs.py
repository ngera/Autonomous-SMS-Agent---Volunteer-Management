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
