"""APScheduler cron jobs for background processing.

Four daily jobs:
- reminder_dispatch (08:00): evaluate customers and send qualifying reminders
- follow_up_dispatch (10:00): follow up on reminders with no response after 48hrs
- strike_decay (00:00): mark strikes >30 days old as decayed
- conversation_expiry (02:00): expire conversations with no activity for 7 days
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, select, update

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.pattern import CustomerAppointmentPattern
from app.models.reminder import Reminder, ReminderStatus
from app.models.strike import ContactStrike
from app.models.suspension import ContactSuspension, ReviewDecision
from app.services.sms import send_sms

logger = get_logger("scheduler")


async def reminder_dispatch() -> None:
    """Daily 08:00 — evaluate customers and send qualifying reminders.

    For each customer with a pattern that has a next_due_date <= today + 3 days:
    1. Check they are not suspended
    2. Check they have opted-in consent
    3. Check no active reminder already exists for this type
    4. Create reminder record and send SMS
    """
    today = date.today()
    lookahead = today + timedelta(days=3)

    async with async_session_factory() as db:
        try:
            # Find patterns with upcoming due dates
            result = await db.execute(
                select(CustomerAppointmentPattern).where(
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
                )
                sent_count += 1

            await db.commit()
            logger.info(
                "Reminder dispatch complete: %d sent, %d skipped",
                sent_count, skipped_count,
            )

        except Exception as e:
            await db.rollback()
            logger.error("Reminder dispatch failed: %s", str(e), exc_info=True)


async def follow_up_dispatch() -> None:
    """Daily 10:00 — follow up on reminders with no response after 48hrs.

    Find reminders that were sent >= 48 hours ago with no follow-up yet
    and no booking conversion. Send a single follow-up message.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Reminder).where(
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
                )
                reminder.follow_up_sent_at = datetime.now(timezone.utc)
                sent_count += 1

            # Mark reminders that still have no response after follow-up
            # (from previous cycle — sent follow-up >= 48hrs ago)
            follow_up_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            await db.execute(
                update(Reminder)
                .where(
                    Reminder.status == ReminderStatus.SENT,
                    Reminder.follow_up_sent_at != None,  # noqa: E711
                    Reminder.follow_up_sent_at <= follow_up_cutoff,
                )
                .values(status=ReminderStatus.NO_RESPONSE)
            )

            await db.commit()
            logger.info("Follow-up dispatch complete: %d sent", sent_count)

        except Exception as e:
            await db.rollback()
            logger.error("Follow-up dispatch failed: %s", str(e), exc_info=True)


async def strike_decay() -> None:
    """Daily 00:00 — mark strikes >30 days old as decayed.

    Strikes older than 30 days no longer count toward the 4-strike suspension
    threshold. We mark them with a decayed_at timestamp.
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

    Active conversations that have had no messages for 7 days are marked
    as expired so they don't interfere with new conversation sessions.
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
