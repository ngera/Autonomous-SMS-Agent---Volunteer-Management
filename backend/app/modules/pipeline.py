"""Inbound SMS processing pipeline.

Implements the 19-step message flow from spec Section 2.2.
Each step can terminate processing early if appropriate.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.booking_history import BookingEventType, BookingHistory, ChangedBy
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import (
    ContactConsent,
    ContactConsentHistory,
    ConsentStatus,
    OptInMethod,
    OptOutMethod,
)
from app.models.conversation import Conversation, ConversationStatus
from app.models.notification import NotificationType
from app.models.strike import ContactStrike
from app.models.strike import ScreenerMethod as StrikeScreenerMethod
from app.models.strike import StrikeClassification
from app.models.suspension import ContactSuspension, SuspensionType
from app.modules.conversation import get_ai_response
from app.modules.screener import Classification, screen_message
from app.services.booking import process_booking_creation
from app.services.notification import create_notification, notify_suspension
from app.services.sms import send_sms

logger = get_logger("pipeline")

# Opt-out keywords for exact matching
OPT_OUT_KEYWORDS = {
    "stop", "unsubscribe", "opt out", "optout", "remove me",
    "do not contact", "leave me alone", "no more messages", "cancel messages",
}

# Yes/No intent for consent flow
YES_INTENT = {"yes", "y", "sure", "ok", "okay", "absolutely", "yep", "yeah", "yea"}
NO_INTENT = {"no", "n", "nope", "don't", "dont", "not interested", "nah"}

STRIKE_MESSAGES = {
    1: "I can only help with booking appointments. Would you like to schedule one?",
    2: "Please keep messages relevant to booking. Further off-topic messages may suspend your access.",
    3: "This is your final warning. Further off-topic messages will suspend your access.",
}

SUSPENSION_MESSAGE = (
    "Your access has been temporarily suspended. "
    "Contact us directly if you believe this is an error."
)

OPT_OUT_CONFIRMATION = (
    "You have been unsubscribed and will receive no further messages. "
    "Contact us directly if you change your mind."
)


async def process_inbound_message(
    db: AsyncSession,
    from_phone: str,
    message_body: str,
) -> None:
    """Process an inbound SMS through the full pipeline."""

    # Step 5: Lookup or create contact
    contact = await _get_or_create_contact(db, from_phone)

    # Step 6: Check suspension status
    if contact.status in (ContactStatus.SUSPENDED, ContactStatus.BANNED):
        logger.info("Message from suspended/banned contact %s — dropping silently", from_phone)
        return

    # Step 7: Check opt-out keywords (before any AI call)
    message_lower = message_body.strip().lower()
    for keyword in OPT_OUT_KEYWORDS:
        if keyword in message_lower:
            await _process_opt_out(db, contact)
            return

    # Step 8: Check consent status
    consent = await _get_consent(db, from_phone)
    if not consent or consent.status != ConsentStatus.OPTED_IN:
        await _handle_consent_flow(db, contact, consent, message_body)
        return

    # Steps 9-10: Pre-screener (Stage 1 rule-based + Stage 2 AI)
    screener_result = await screen_message(message_body, db)

    if screener_result.is_opt_out:
        await _process_opt_out(db, contact)
        return

    if screener_result.classification in (Classification.IRRELEVANT, Classification.ABUSIVE):
        await _handle_strike(
            db, contact, message_body,
            screener_result.classification,
            screener_result.method.value,
        )
        return

    # Step 11 handled inside _handle_strike

    # Steps 12-13: Load/create conversation and fetch dynamic context
    conversation = await _get_or_create_conversation(db, from_phone)

    # Steps 14-15: Call full conversation AI
    ai_response = await get_ai_response(
        db=db,
        contact_phone=from_phone,
        message_history=conversation.message_history or [],
        user_message=message_body,
    )

    # Step 16-17: If booking confirmed, create booking
    if ai_response.booking_confirmed and ai_response.appointment_type_id:
        booking = Booking(
            contact_phone=from_phone,
            appointment_type_id=ai_response.appointment_type_id,
            scheduled_at=ai_response.slot_datetime,
            price_at_booking=ai_response.total_price or 0,
            status=BookingStatus.SCHEDULED,
            confirmed_at=datetime.now(timezone.utc),
            conversation_id=conversation.id,
        )
        db.add(booking)
        await db.flush()

        # Record history
        history = BookingHistory(
            booking_id=booking.id,
            event_type=BookingEventType.CREATED,
            new_status=BookingStatus.SCHEDULED,
            new_scheduled_at=ai_response.slot_datetime,
            changed_by=ChangedBy.USER_SMS,
        )
        db.add(history)
        await db.flush()

        # Calendar event, ICS URLs, SMS handled by booking service
        await process_booking_creation(db, booking)

        # Mark conversation as completed
        conversation.status = ConversationStatus.COMPLETED

        # Create admin notification
        await create_notification(
            db=db,
            notification_type=NotificationType.NEW_BOOKING,
            title=f"New booking from {from_phone}",
            body=f"Booking confirmed via SMS conversation",
            reference_id=booking.id,
            reference_type="booking",
        )
    else:
        # Step 18: Send SMS response
        await send_sms(to=from_phone, body=ai_response.message_to_user)

    # Step 19: Save conversation history
    history_entry = {
        "role": "user",
        "content": message_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assistant_entry = {
        "role": "assistant",
        "content": ai_response.message_to_user,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    updated_history = list(conversation.message_history or [])
    updated_history.append(history_entry)
    updated_history.append(assistant_entry)
    conversation.message_history = updated_history
    conversation.last_message_at = datetime.now(timezone.utc)

    await db.flush()


async def _get_or_create_contact(db: AsyncSession, phone: str) -> Contact:
    result = await db.execute(select(Contact).where(Contact.phone == phone))
    contact = result.scalar_one_or_none()
    if not contact:
        contact = Contact(phone=phone)
        db.add(contact)
        # Also create consent record
        consent = ContactConsent(
            contact_phone=phone,
            status=ConsentStatus.UNCONTACTED,
        )
        db.add(consent)
        await db.flush()
    return contact


async def _get_consent(db: AsyncSession, phone: str) -> ContactConsent | None:
    result = await db.execute(
        select(ContactConsent).where(ContactConsent.contact_phone == phone)
    )
    return result.scalar_one_or_none()


async def _process_opt_out(db: AsyncSession, contact: Contact) -> None:
    """Process opt-out: update consent, send confirmation, stop."""
    consent = await _get_consent(db, contact.phone)
    if consent:
        old_status = consent.status
        consent.status = ConsentStatus.OPTED_OUT
        consent.opted_out_at = datetime.now(timezone.utc)
        consent.opt_out_method = OptOutMethod.SMS_STOP
        consent.last_status_change_at = datetime.now(timezone.utc)

        # Record history
        history = ContactConsentHistory(
            contact_phone=contact.phone,
            previous_status=old_status,
            new_status=ConsentStatus.OPTED_OUT,
            changed_at=datetime.now(timezone.utc),
            changed_by_phone=contact.phone,
            reason="User sent opt-out keyword via SMS",
        )
        db.add(history)

    await send_sms(to=contact.phone, body=OPT_OUT_CONFIRMATION)

    # Create notification
    await create_notification(
        db=db,
        notification_type=NotificationType.OPT_OUT,
        title=f"Customer opted out: {contact.phone}",
        body="Customer sent opt-out keyword via SMS",
    )

    await db.flush()
    logger.info("Processed opt-out for %s", contact.phone)


async def _handle_consent_flow(
    db: AsyncSession,
    contact: Contact,
    consent: ContactConsent | None,
    message: str,
) -> None:
    """Handle messages from users who haven't opted in yet."""
    if not consent:
        return

    if consent.status == ConsentStatus.PENDING:
        # Check if reply is YES or NO
        msg_lower = message.strip().lower()

        if msg_lower in YES_INTENT:
            consent.status = ConsentStatus.OPTED_IN
            consent.opted_in_at = datetime.now(timezone.utc)
            consent.opt_in_method = OptInMethod.SMS_REPLY
            consent.last_status_change_at = datetime.now(timezone.utc)

            history = ContactConsentHistory(
                contact_phone=contact.phone,
                previous_status=ConsentStatus.PENDING,
                new_status=ConsentStatus.OPTED_IN,
                changed_at=datetime.now(timezone.utc),
                changed_by_phone=contact.phone,
                reason="User replied YES to opt-in SMS",
            )
            db.add(history)
            await db.flush()

            await send_sms(
                to=contact.phone,
                body=(
                    f"Thanks for opting in to {settings.business_name}! "
                    "You can now book appointments by sending us a message. "
                    "Reply STOP at any time to unsubscribe."
                ),
            )

        elif msg_lower in NO_INTENT:
            consent.status = ConsentStatus.OPTED_OUT
            consent.opted_out_at = datetime.now(timezone.utc)
            consent.opt_out_method = OptOutMethod.SMS_REPLY
            consent.last_status_change_at = datetime.now(timezone.utc)

            history = ContactConsentHistory(
                contact_phone=contact.phone,
                previous_status=ConsentStatus.PENDING,
                new_status=ConsentStatus.OPTED_OUT,
                changed_at=datetime.now(timezone.utc),
                changed_by_phone=contact.phone,
                reason="User replied NO to opt-in SMS",
            )
            db.add(history)
            await db.flush()

            await send_sms(
                to=contact.phone,
                body="No problem. You won't receive any further messages from us.",
            )
        else:
            await send_sms(
                to=contact.phone,
                body="Please reply YES to opt in to appointment messages, or NO to decline.",
            )

    # For UNCONTACTED or OPTED_OUT, do nothing (no unsolicited messages)


async def _handle_strike(
    db: AsyncSession,
    contact: Contact,
    message: str,
    classification: Classification,
    screener_method: str,
) -> None:
    """Record a strike and take escalation action."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Count active (non-decayed) strikes
    active_strikes_result = await db.execute(
        select(func.count()).where(
            ContactStrike.contact_phone == contact.phone,
            ContactStrike.decayed_at.is_(None),
            ContactStrike.created_at >= thirty_days_ago,
        )
    )
    active_count = active_strikes_result.scalar() or 0
    new_strike_number = active_count + 1

    # Map classification
    strike_class = StrikeClassification.ABUSIVE if classification == Classification.ABUSIVE else StrikeClassification.IRRELEVANT
    method = StrikeScreenerMethod.RULE_BASED if screener_method == "rule_based" else StrikeScreenerMethod.AI_MICRO_PROMPT

    # Record strike
    strike = ContactStrike(
        contact_phone=contact.phone,
        strike_number=new_strike_number,
        message_content=message,
        classification=strike_class,
        screener_method=method,
        screener_response=classification.value,
    )
    db.add(strike)
    await db.flush()

    # Immediate suspension for ABUSIVE
    if classification == Classification.ABUSIVE:
        await _suspend_contact(db, contact, strike, "Abusive message detected")
        await send_sms(to=contact.phone, body=SUSPENSION_MESSAGE)
        return

    # Strike escalation for IRRELEVANT
    if new_strike_number >= 4:
        await _suspend_contact(db, contact, strike, f"Strike {new_strike_number}: repeated irrelevant messages")
        await send_sms(to=contact.phone, body=SUSPENSION_MESSAGE)
    elif new_strike_number in STRIKE_MESSAGES:
        await send_sms(to=contact.phone, body=STRIKE_MESSAGES[new_strike_number])

    # Strike 3 warning notification
    if new_strike_number == 3:
        await create_notification(
            db=db,
            notification_type=NotificationType.STRIKE_WARNING,
            title=f"Strike 3 issued: {contact.phone}",
            body="Final warning sent — next offense will suspend the account",
        )

    await db.flush()


async def _suspend_contact(
    db: AsyncSession,
    contact: Contact,
    strike: ContactStrike,
    reason: str,
) -> None:
    """Suspend a contact and notify admins."""
    contact.status = ContactStatus.SUSPENDED

    # Update consent
    consent = await _get_consent(db, contact.phone)
    if consent:
        consent.status = ConsentStatus.BLOCKED
        consent.last_status_change_at = datetime.now(timezone.utc)

    # Get active conversation if any
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.contact_phone == contact.phone,
            Conversation.status == ConversationStatus.ACTIVE,
        )
    )
    active_conv = conv_result.scalar_one_or_none()

    # Collect recent strike IDs
    strikes_result = await db.execute(
        select(ContactStrike.id).where(
            ContactStrike.contact_phone == contact.phone,
            ContactStrike.decayed_at.is_(None),
        )
    )
    strike_ids = [row[0] for row in strikes_result.all()]

    suspension = ContactSuspension(
        contact_phone=contact.phone,
        suspension_type=SuspensionType.AUTO_ABUSIVE
        if strike.classification == StrikeClassification.ABUSIVE
        else SuspensionType.AUTO_STRIKE,
        reason=reason,
        strike_ids=strike_ids,
        conversation_id=active_conv.id if active_conv else None,
        notification_sent_at=datetime.now(timezone.utc),
    )
    db.add(suspension)
    await db.flush()

    # Notify admins
    await notify_suspension(db, contact.phone, suspension.id, reason)

    logger.warning("Contact %s suspended: %s", contact.phone, reason)


async def _get_or_create_conversation(db: AsyncSession, phone: str) -> Conversation:
    """Get active conversation or create a new one."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.contact_phone == phone,
            Conversation.status == ConversationStatus.ACTIVE,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            contact_phone=phone,
            message_history=[],
            current_step="greeting",
            status=ConversationStatus.ACTIVE,
            consent_verified_at=datetime.now(timezone.utc),
        )
        db.add(conversation)
        await db.flush()

    return conversation
