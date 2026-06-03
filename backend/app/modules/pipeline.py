"""Inbound SMS processing pipeline.

Implements the 19-step message flow from spec Section 2.2.
Each step can terminate processing early if appropriate.

Admin SMS messages bypass the customer pipeline (no screener, consent, or strikes)
and are routed to the admin tool_use conversation.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
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
from app.modules.conversation import (
    get_ai_response_with_tools,
    trim_message_history,
)
from app.modules.memory_extraction import extract_and_save_memory
from app.modules.screener import Classification, screen_message
from app.services.notification import create_notification, notify_suspension
from app.models.tenant import Tenant
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

# Polite first-warning for ABUSIVE classification. Tenant-overridable
# via `suspension_abusive_warning_message`. The default
# `max_abusive_strikes=2` means: send this on the 1st abuse, suspend on
# the 2nd.
ABUSIVE_WARNING_MESSAGE = (
    "We can't accept messages with that language. "
    "Please keep your messages respectful — another message like this "
    "will suspend your access."
)

SUSPENSION_MESSAGE = (
    "Your access has been temporarily suspended. "
    "Contact us directly if you believe this is an error."
)

OPT_OUT_CONFIRMATION = (
    "You have been unsubscribed and will receive no further messages. "
    "Contact us directly if you change your mind."
)


# ── Admin detection ──


async def _check_admin_phone(
    db: AsyncSession, phone: str, tenant_id: uuid.UUID | None,
) -> AdminUser | None:
    """Check if the phone belongs to an active admin user."""
    if not tenant_id:
        return None
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.phone == phone,
            AdminUser.tenant_id == tenant_id,
            AdminUser.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


# ── Admin message processing ──


async def _process_admin_message(
    db: AsyncSession,
    from_phone: str,
    message_body: str,
    tenant: Tenant,
    admin_user: AdminUser,
) -> None:
    """Process an SMS from an admin user — no screener, consent, or strikes."""
    tenant_id = tenant.id

    # Get or create admin conversation (separate from customer convos via sender_type)
    conversation = await _get_or_create_conversation(
        db, from_phone, tenant_id=tenant_id,
        contact_id=None, sender_type="admin",
    )

    # Server-side intent routers for recruitment intents — the LLM has
    # consistently failed to invoke approve_recruitment_campaign,
    # recruitment_status, start_recruitment_campaign,
    # delete_recruitment_campaign, AND manage_specific_date_slot/list
    # despite explicit prompt rules, so we short-circuit unambiguous
    # phrases here. See design_decisions.md #7, #20, #21.
    from app.agents.recruiter.chat_tools import (
        maybe_handle_approval_directly,
        maybe_handle_delete_campaign_directly,
        maybe_handle_list_events_directly,
        maybe_handle_start_campaign_directly,
        maybe_handle_status_directly,
    )
    from app.modules.tool_handlers import ToolContext as _ToolContext

    auto_reply = await maybe_handle_approval_directly(
        db, tenant, message_body, admin_user
    )
    if auto_reply is None:
        auto_reply = await maybe_handle_status_directly(
            db, tenant, message_body
        )
    if auto_reply is None:
        # Start + delete + list-events routers need a ToolContext
        # shaped like the chat tool would have built. Admin path:
        # contact_phone is the admin's phone, contact_id is the admin's
        # user id (same convention as the LLM tool-use loop below).
        _admin_ctx = _ToolContext(
            db=db,
            tenant=tenant,
            contact_phone=from_phone,
            contact_id=admin_user.id,
            is_admin=True,
        )
        # List-events is checked first — its patterns are unambiguous
        # ("list/show upcoming events") and would otherwise be lost
        # to the LLM answering from preamble memory.
        auto_reply = await maybe_handle_list_events_directly(
            _admin_ctx, message_body
        )
        if auto_reply is None:
            # Delete BEFORE start: some delete phrasings
            # (e.g., "delete the recruitment for X") could be
            # mis-parsed by the start router's softer "recruit for X".
            auto_reply = await maybe_handle_delete_campaign_directly(
                _admin_ctx, message_body
            )
        if auto_reply is None:
            auto_reply = await maybe_handle_start_campaign_directly(
                _admin_ctx, message_body
            )
        if auto_reply is None:
            # Tier 2: Haiku intent classifier. Catches novel phrasings
            # the regex didn't recognize ("scrap the food drive plan",
            # "we're full for Saturday — kill outreach", etc.) without
            # letting them slip through to the full LLM where they
            # historically caused hallucinated confirmations.
            # See design_decisions.md #22.
            from app.agents.orchestrator.intent_dispatch import (
                maybe_handle_via_classifier,
            )
            auto_reply = await maybe_handle_via_classifier(
                db, tenant, message_body, admin_user, _admin_ctx
            )
    if auto_reply is not None:
        await send_sms(to=from_phone, body=auto_reply, tenant=tenant)
        now = datetime.now(timezone.utc)
        updated_history = list(conversation.message_history or [])
        updated_history.append({
            "role": "user",
            "content": message_body,
            "timestamp": now.isoformat(),
        })
        updated_history.append({
            "role": "assistant",
            "content": auto_reply,
            "timestamp": now.isoformat(),
        })
        conversation.message_history = trim_message_history(updated_history)
        conversation.last_message_at = now
        await db.flush()
        logger.info(
            "Admin SMS auto-routed recruitment intent for %s (admin: %s)",
            from_phone, admin_user.email,
        )
        return

    # Call AI with admin tools
    ai_response = await get_ai_response_with_tools(
        db=db,
        contact_phone=from_phone,
        contact_id=admin_user.id,  # Use admin user ID as contact_id for context
        message_history=conversation.message_history or [],
        user_message=message_body,
        tenant=tenant,
        is_admin=True,
    )

    # Send response SMS
    await send_sms(to=from_phone, body=ai_response.message_to_user, tenant=tenant)

    # Save conversation history
    now = datetime.now(timezone.utc)
    updated_history = list(conversation.message_history or [])
    updated_history.append({
        "role": "user",
        "content": message_body,
        "timestamp": now.isoformat(),
    })
    updated_history.append({
        "role": "assistant",
        "content": ai_response.message_to_user,
        "timestamp": now.isoformat(),
    })
    conversation.message_history = trim_message_history(updated_history)
    conversation.last_message_at = now

    await db.flush()
    logger.info("Admin message processed for %s (admin: %s)", from_phone, admin_user.email)


# ── Main pipeline ──


async def process_inbound_message(
    db: AsyncSession,
    from_phone: str,
    message_body: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Process an inbound SMS through the full pipeline."""

    # Load tenant
    tenant: Tenant | None = None
    if tenant_id:
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()

    # ── Phase 1 routing matrix (Row 6 Edge E) ─────────────────────
    # SUPER_ADMIN cross-tenant detection runs BEFORE the standard
    # tenant-scoped admin lookup. SUPER_ADMINs get a rejection reply
    # pointing them at the dashboard.
    super_admin_result = await db.execute(
        select(AdminUser).where(
            AdminUser.phone == from_phone,
            AdminUser.role == AdminRole.SUPER_ADMIN,
            AdminUser.is_active.is_(True),
        )
    )
    super_admin_user = super_admin_result.scalar_one_or_none()
    if super_admin_user and tenant:
        from app.agents.orchestrator.admin_dispatch import (
            super_admin_phone_rejection,
        )
        # Reuse super_admin_user but with tenant context (for prompt lookup).
        super_admin_user.tenant_id = tenant.id  # ephemeral, not persisted
        reply = await super_admin_phone_rejection(db, admin=super_admin_user)
        await send_sms(to=from_phone, body=reply, tenant=tenant)
        return

    # ── Phase 1 routing matrix (Row 4/5) ──────────────────────────
    # If the phone is unknown (no Contact match) AND not a tenant admin,
    # route to the candidate path BEFORE _get_or_create_contact would
    # silently create a UNCONTACTED stub.
    existing_contact = None
    if tenant_id:
        existing_result = await db.execute(
            select(Contact).where(
                Contact.tenant_id == tenant_id,
                Contact.phone == from_phone,
            )
        )
        existing_contact = existing_result.scalar_one_or_none()

    existing_admin = await _check_admin_phone(db, from_phone, tenant_id)

    if existing_contact is None and existing_admin is None and tenant_id:
        from app.services.candidate_pipeline import handle_unknown_phone_inbound
        await handle_unknown_phone_inbound(
            db,
            phone=from_phone,
            message_body=message_body,
            tenant_id=tenant_id,
        )
        await db.flush()
        return

    # Step 5: Lookup or create contact (now only fires for existing Contacts
    # or the edge case where tenant_id is None).
    contact = await _get_or_create_contact(db, from_phone, tenant_id=tenant_id)

    # Step 5.5: Check if sender is an admin
    admin_user = existing_admin or await _check_admin_phone(db, from_phone, tenant_id)
    if admin_user and tenant:
        # Phase 1 step 4: try admin SMS commands first; fall through
        # to existing tool_use admin pipeline if no command matched.
        from app.agents.orchestrator.admin_dispatch import (
            maybe_handle_admin_command,
        )
        cmd_reply = await maybe_handle_admin_command(
            db, admin=admin_user, message_body=message_body
        )
        if cmd_reply is not None:
            await send_sms(to=from_phone, body=cmd_reply, tenant=tenant)
            await db.flush()
            return
        await _process_admin_message(db, from_phone, message_body, tenant, admin_user)
        return

    # Step 6: Check suspension status
    if contact.status in (ContactStatus.SUSPENDED, ContactStatus.BANNED):
        logger.info("Message from suspended/banned contact %s — sending suspension notice", from_phone)
        await send_sms(
            to=from_phone,
            body="Your access is currently suspended. Please contact us directly for assistance.",
            tenant=tenant,
        )
        return

    # Step 7: Check opt-out keywords (before any AI call)
    message_lower = message_body.strip().lower()
    for keyword in OPT_OUT_KEYWORDS:
        if keyword in message_lower:
            await _process_opt_out(db, contact, tenant=tenant, tenant_id=tenant_id)
            return

    # Step 8: Check consent status
    consent = await _get_consent(db, from_phone, tenant_id=tenant_id)
    if not consent or consent.status != ConsentStatus.OPTED_IN:
        await _handle_consent_flow(db, contact, consent, message_body, tenant=tenant, tenant_id=tenant_id)
        return

    # Steps 9-10: Pre-screener (Stage 1 rule-based + Stage 2 AI)
    # Fetch active conversation context so the screener can evaluate
    # short replies like "yes" / "tomorrow" in context.
    conv_query = (
        select(Conversation)
        .where(
            Conversation.contact_phone == from_phone,
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.sender_type == "customer",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    if tenant_id:
        conv_query = conv_query.where(Conversation.tenant_id == tenant_id)
    conv_result = await db.execute(conv_query)
    active_conversation = conv_result.scalar_one_or_none()

    conversation_history = active_conversation.message_history if active_conversation else None

    screener_result = await screen_message(
        message_body, db, tenant=tenant,
        contact_id=contact.id, contact_phone=from_phone,
        conversation_history=conversation_history,
    )

    if screener_result.is_opt_out:
        await _process_opt_out(db, contact, tenant=tenant, tenant_id=tenant_id)
        return

    if screener_result.classification in (Classification.IRRELEVANT, Classification.ABUSIVE):
        await _handle_strike(
            db, contact, message_body,
            screener_result.classification,
            screener_result.method.value,
            tenant=tenant,
            tenant_id=tenant_id,
        )
        return

    # Steps 12-13: Load/create conversation
    conversation = active_conversation or await _get_or_create_conversation(db, from_phone, tenant_id=tenant_id, contact_id=contact.id)

    # ── Phase 1: Engagement intent routers (Row 1 — check in / check out) ──
    # Server-side short-circuit per design-decision #7. These check the
    # message for HERE/DONE/SWITCH/ALSO and apply state mutations
    # directly, bypassing the LLM. Pending-intent disambiguation
    # (multi-booking picker, re-entry confirmation) also handled here.
    from app.agents.engagement.intents import (
        maybe_handle_here_check_in,
        maybe_handle_check_out,
        maybe_handle_reentry,
        maybe_handle_service_switch,
        maybe_handle_service_add,
    )

    # Re-entry handler runs first when a pending intent exists for re-entry.
    engagement_reply = await maybe_handle_reentry(
        db, contact=contact, conversation=conversation, message_body=message_body
    )
    # Phase 3 SWITCH/ALSO routed before HERE/DONE so e.g. "switch to cooking"
    # doesn't accidentally match the "here" word inside "where".
    if engagement_reply is None:
        engagement_reply = await maybe_handle_service_switch(
            db, contact=contact, conversation=conversation, message_body=message_body
        )
    if engagement_reply is None:
        engagement_reply = await maybe_handle_service_add(
            db, contact=contact, conversation=conversation, message_body=message_body
        )
    if engagement_reply is None:
        engagement_reply = await maybe_handle_here_check_in(
            db, contact=contact, conversation=conversation, message_body=message_body
        )
    if engagement_reply is None:
        engagement_reply = await maybe_handle_check_out(
            db, contact=contact, conversation=conversation, message_body=message_body
        )
    # Tier 2 — Haiku intent classifier catches long-tail phrasings the
    # regex routers miss ("im finally here lol", "leaving now", "moving
    # over to setup"). Soft-fails on API errors / low confidence and falls
    # through to the full customer LLM. See engagement.intent_classifier.
    if engagement_reply is None:
        from app.agents.engagement.intent_dispatch import (
            maybe_handle_via_classifier as maybe_handle_engagement_via_classifier,
        )
        engagement_reply = await maybe_handle_engagement_via_classifier(
            db,
            tenant=tenant,
            contact=contact,
            conversation=conversation,
            message_body=message_body,
        )
    if engagement_reply is not None:
        await send_sms(to=from_phone, body=engagement_reply, tenant=tenant)
        now = datetime.now(timezone.utc)
        updated_history = list(conversation.message_history or [])
        updated_history.append({
            "role": "user", "content": message_body, "timestamp": now.isoformat(),
        })
        updated_history.append({
            "role": "assistant", "content": engagement_reply, "timestamp": now.isoformat(),
        })
        conversation.message_history = trim_message_history(updated_history)
        conversation.last_message_at = now
        await db.flush()
        return

    # Steps 14-15: Call conversation AI with tool_use
    ai_response = await get_ai_response_with_tools(
        db=db,
        contact_phone=from_phone,
        contact_id=contact.id,
        message_history=conversation.message_history or [],
        user_message=message_body,
        tenant=tenant,
        is_admin=False,
    )

    # Step 16-17: Check if a booking was created by the tool handler
    if ai_response.booking_created:
        # Mark conversation as completed
        conversation.status = ConversationStatus.COMPLETED

        # Create admin notification
        await create_notification(
            db=db,
            notification_type=NotificationType.NEW_BOOKING,
            title=f"New booking from {from_phone}",
            body="Booking confirmed via SMS conversation",
            reference_id=None,
            reference_type="booking",
            tenant_id=tenant_id,
        )

    # Step 18: Send SMS response (always — tool handler suppresses the old SMS,
    # so Claude's text response IS the confirmation message)
    await send_sms(to=from_phone, body=ai_response.message_to_user, tenant=tenant)

    # Step 19: Save conversation history
    now = datetime.now(timezone.utc)
    updated_history = list(conversation.message_history or [])
    updated_history.append({
        "role": "user",
        "content": message_body,
        "timestamp": now.isoformat(),
    })
    updated_history.append({
        "role": "assistant",
        "content": ai_response.message_to_user,
        "timestamp": now.isoformat(),
    })
    conversation.message_history = trim_message_history(updated_history)
    conversation.last_message_at = now

    await db.flush()

    # Long-term memory extraction — fire-and-forget after a booking closes
    # the conversation. Runs on its own DB session so it doesn't block the
    # SMS response path or share state with this request.
    if ai_response.booking_created and tenant_id:
        asyncio.create_task(
            extract_and_save_memory(
                contact_id=contact.id,
                tenant_id=tenant_id,
                message_history=updated_history,
            )
        )


async def _get_or_create_contact(
    db: AsyncSession, phone: str, tenant_id: uuid.UUID | None = None
) -> Contact:
    query = select(Contact).where(Contact.phone == phone)
    if tenant_id:
        query = query.where(Contact.tenant_id == tenant_id)
    result = await db.execute(query)
    contact = result.scalar_one_or_none()
    if not contact:
        contact = Contact(phone=phone, tenant_id=tenant_id)
        db.add(contact)
        await db.flush()
        # Also create consent record
        consent = ContactConsent(
            contact_phone=phone,
            contact_id=contact.id,
            status=ConsentStatus.UNCONTACTED,
            tenant_id=tenant_id,
        )
        db.add(consent)
        await db.flush()
    return contact


async def _get_consent(
    db: AsyncSession, phone: str, tenant_id: uuid.UUID | None = None
) -> ContactConsent | None:
    query = select(ContactConsent).where(ContactConsent.contact_phone == phone)
    if tenant_id:
        query = query.where(ContactConsent.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _process_opt_out(
    db: AsyncSession,
    contact: Contact,
    tenant: "Tenant | None" = None,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Process opt-out: update consent, send confirmation, stop."""
    consent = await _get_consent(db, contact.phone, tenant_id=tenant_id)
    if consent:
        old_status = consent.status
        consent.status = ConsentStatus.OPTED_OUT
        consent.opted_out_at = datetime.now(timezone.utc)
        consent.opt_out_method = OptOutMethod.SMS_STOP
        consent.last_status_change_at = datetime.now(timezone.utc)

        # Record history
        history = ContactConsentHistory(
            tenant_id=tenant_id,
            contact_id=contact.id,
            contact_phone=contact.phone,
            previous_status=old_status,
            new_status=ConsentStatus.OPTED_OUT,
            changed_at=datetime.now(timezone.utc),
            changed_by_phone=contact.phone,
            reason="User sent opt-out keyword via SMS",
        )
        db.add(history)

    await send_sms(to=contact.phone, body=OPT_OUT_CONFIRMATION, tenant=tenant)

    # Create notification
    await create_notification(
        db=db,
        notification_type=NotificationType.OPT_OUT,
        title=f"Customer opted out: {contact.phone}",
        body="Customer sent opt-out keyword via SMS",
        tenant_id=tenant_id,
    )

    await db.flush()
    logger.info("Processed opt-out for %s", contact.phone)


async def _handle_consent_flow(
    db: AsyncSession,
    contact: Contact,
    consent: ContactConsent | None,
    message: str,
    tenant: "Tenant | None" = None,
    tenant_id: uuid.UUID | None = None,
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
                tenant_id=tenant_id,
                contact_id=contact.id,
                contact_phone=contact.phone,
                previous_status=ConsentStatus.PENDING,
                new_status=ConsentStatus.OPTED_IN,
                changed_at=datetime.now(timezone.utc),
                changed_by_phone=contact.phone,
                reason="User replied YES to opt-in SMS",
            )
            db.add(history)
            await db.flush()

            business_name = tenant.business_name if tenant else settings.business_name
            await send_sms(
                to=contact.phone,
                body=(
                    f"Thanks for opting in to {business_name}! "
                    "You can now book appointments by sending us a message. "
                    "Reply STOP at any time to unsubscribe."
                ),
                tenant=tenant,
            )

        elif msg_lower in NO_INTENT:
            consent.status = ConsentStatus.OPTED_OUT
            consent.opted_out_at = datetime.now(timezone.utc)
            consent.opt_out_method = OptOutMethod.SMS_REPLY
            consent.last_status_change_at = datetime.now(timezone.utc)

            history = ContactConsentHistory(
                tenant_id=tenant_id,
                contact_id=contact.id,
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
                tenant=tenant,
            )
        else:
            await send_sms(
                to=contact.phone,
                body="Please reply YES to opt in to appointment messages, or NO to decline.",
                tenant=tenant,
            )

    # For UNCONTACTED or OPTED_OUT, do nothing (no unsolicited messages)


async def _get_suspension_settings(db: AsyncSession, tenant_id: uuid.UUID | None) -> dict:
    """Load tenant-specific suspension settings with defaults."""
    from app.models.system_setting import SystemSetting

    defaults = {
        "max_strikes": 4,
        "strike_decay_days": 30,
        "auto_suspend_abusive": True,
        # Threshold for ABUSIVE classification specifically. 2 = warn on
        # the 1st abusive message, suspend on the 2nd. Only applies when
        # auto_suspend_abusive=True; otherwise abusive strikes count
        # against the IRRELEVANT max_strikes threshold.
        "max_abusive_strikes": 2,
        "suspension_message": SUSPENSION_MESSAGE,
        "abusive_warning_message": ABUSIVE_WARNING_MESSAGE,
        "strike_message_1": STRIKE_MESSAGES.get(1, ""),
        "strike_message_2": STRIKE_MESSAGES.get(2, ""),
        "strike_message_3": STRIKE_MESSAGES.get(3, ""),
    }
    if not tenant_id:
        return defaults

    keys = [f"suspension_{k}" for k in defaults]
    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key.in_(keys),
        )
    )
    for setting in result.scalars().all():
        short_key = setting.key.replace("suspension_", "", 1)
        if short_key in ("max_strikes", "strike_decay_days", "max_abusive_strikes"):
            try:
                defaults[short_key] = int(setting.value)
            except ValueError:
                pass
        elif short_key == "auto_suspend_abusive":
            defaults[short_key] = setting.value.lower() in ("true", "1", "yes")
        else:
            defaults[short_key] = setting.value

    return defaults


async def _handle_strike(
    db: AsyncSession,
    contact: Contact,
    message: str,
    classification: Classification,
    screener_method: str,
    tenant: "Tenant | None" = None,
    tenant_id: uuid.UUID | None = None,
    test_mode: bool = False,
) -> None:
    """Record a strike and take escalation action."""
    cfg = await _get_suspension_settings(db, tenant_id)
    max_strikes = cfg["max_strikes"]
    decay_days = cfg["strike_decay_days"]
    auto_suspend_abusive = cfg["auto_suspend_abusive"]
    max_abusive_strikes = cfg["max_abusive_strikes"]
    suspension_msg = cfg["suspension_message"]
    abusive_warning_msg = cfg["abusive_warning_message"]
    strike_messages = {
        i: cfg[f"strike_message_{i}"]
        for i in (1, 2, 3)
        if cfg.get(f"strike_message_{i}")
    }

    now = datetime.now(timezone.utc)
    decay_cutoff = now - timedelta(days=decay_days)

    # Count active (non-decayed) strikes (any classification)
    strike_query = select(func.count()).where(
        ContactStrike.contact_phone == contact.phone,
        ContactStrike.decayed_at.is_(None),
        ContactStrike.created_at >= decay_cutoff,
    )
    if tenant_id:
        strike_query = strike_query.where(ContactStrike.tenant_id == tenant_id)
    active_strikes_result = await db.execute(strike_query)
    active_count = active_strikes_result.scalar() or 0
    new_strike_number = active_count + 1

    # Map classification
    strike_class = StrikeClassification.ABUSIVE if classification == Classification.ABUSIVE else StrikeClassification.IRRELEVANT
    method = StrikeScreenerMethod.RULE_BASED if screener_method == "rule_based" else StrikeScreenerMethod.AI_MICRO_PROMPT

    # Record strike
    strike = ContactStrike(
        contact_phone=contact.phone,
        contact_id=contact.id,
        tenant_id=tenant_id,
        strike_number=new_strike_number,
        message_content=message,
        classification=strike_class,
        screener_method=method,
        screener_response=classification.value,
    )
    db.add(strike)
    await db.flush()

    # ── ABUSIVE branch ──
    # Default behavior: warn on the 1st abusive message, suspend on the
    # 2nd (max_abusive_strikes=2). Tenant can flip auto_suspend_abusive
    # off to make abusive count toward the IRRELEVANT max_strikes threshold
    # instead.
    if classification == Classification.ABUSIVE and auto_suspend_abusive:
        abusive_query = select(func.count()).where(
            ContactStrike.contact_phone == contact.phone,
            ContactStrike.classification == StrikeClassification.ABUSIVE,
            ContactStrike.decayed_at.is_(None),
            ContactStrike.created_at >= decay_cutoff,
        )
        if tenant_id:
            abusive_query = abusive_query.where(
                ContactStrike.tenant_id == tenant_id
            )
        active_abusive_count = (
            await db.execute(abusive_query)
        ).scalar() or 0

        if active_abusive_count >= max_abusive_strikes:
            await _suspend_contact(
                db, contact, strike,
                f"Abusive language (strike {active_abusive_count}/{max_abusive_strikes})",
                tenant=tenant, tenant_id=tenant_id,
                triggering_message=message,
            )
            if not test_mode:
                await send_sms(to=contact.phone, body=suspension_msg, tenant=tenant)
        else:
            # First abusive strike → polite warning, no suspension.
            if not test_mode:
                await send_sms(
                    to=contact.phone, body=abusive_warning_msg, tenant=tenant,
                )
            # Admin notification so the team knows abuse is brewing.
            await create_notification(
                db=db,
                notification_type=NotificationType.STRIKE_WARNING,
                title=f"Abusive message warning: {contact.phone}",
                body=(
                    f"Warning sent — next abusive message will suspend the "
                    f"account (threshold: {max_abusive_strikes})."
                ),
                tenant_id=tenant_id,
            )
        await db.flush()
        return

    # ── IRRELEVANT branch (or ABUSIVE when auto_suspend_abusive is off) ──
    if new_strike_number >= max_strikes:
        await _suspend_contact(db, contact, strike, f"Strike {new_strike_number}: repeated irrelevant messages", tenant=tenant, tenant_id=tenant_id, triggering_message=message)
        if not test_mode:
            await send_sms(to=contact.phone, body=suspension_msg, tenant=tenant)
    elif new_strike_number in strike_messages:
        if not test_mode:
            await send_sms(to=contact.phone, body=strike_messages[new_strike_number], tenant=tenant)

    # Warning notification one strike before suspension
    if new_strike_number == max_strikes - 1:
        await create_notification(
            db=db,
            notification_type=NotificationType.STRIKE_WARNING,
            title=f"Strike {new_strike_number} issued: {contact.phone}",
            body=f"Final warning sent — next offense will suspend the account (threshold: {max_strikes})",
            tenant_id=tenant_id,
        )

    await db.flush()


async def _suspend_contact(
    db: AsyncSession,
    contact: Contact,
    strike: ContactStrike,
    reason: str,
    tenant: "Tenant | None" = None,
    tenant_id: uuid.UUID | None = None,
    triggering_message: str | None = None,
) -> None:
    """Suspend a contact and notify admins."""
    contact.status = ContactStatus.SUSPENDED

    # Update consent
    consent = await _get_consent(db, contact.phone, tenant_id=tenant_id)
    if consent:
        consent.status = ConsentStatus.BLOCKED
        consent.last_status_change_at = datetime.now(timezone.utc)

    # Get active conversation if any (may have multiple — pick the most recent)
    conv_query = (
        select(Conversation)
        .where(
            Conversation.contact_phone == contact.phone,
            Conversation.status == ConversationStatus.ACTIVE,
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    if tenant_id:
        conv_query = conv_query.where(Conversation.tenant_id == tenant_id)
    conv_result = await db.execute(conv_query)
    active_conv = conv_result.scalar_one_or_none()

    # Collect recent strike IDs
    strike_query = select(ContactStrike.id).where(
        ContactStrike.contact_phone == contact.phone,
        ContactStrike.decayed_at.is_(None),
    )
    if tenant_id:
        strike_query = strike_query.where(ContactStrike.tenant_id == tenant_id)
    strikes_result = await db.execute(strike_query)
    strike_ids = [row[0] for row in strikes_result.all()]

    suspension = ContactSuspension(
        contact_phone=contact.phone,
        contact_id=contact.id,
        tenant_id=tenant_id,
        suspension_type=SuspensionType.AUTO_ABUSIVE
        if strike.classification == StrikeClassification.ABUSIVE
        else SuspensionType.AUTO_STRIKE,
        reason=reason,
        triggering_message=triggering_message,
        strike_ids=strike_ids,
        conversation_id=active_conv.id if active_conv else None,
        notification_sent_at=datetime.now(timezone.utc),
    )
    db.add(suspension)
    await db.flush()

    # Notify admins
    await notify_suspension(db, contact.phone, suspension.id, reason, tenant_id=tenant_id)

    logger.warning("Contact %s suspended: %s", contact.phone, reason)


async def _get_or_create_conversation(
    db: AsyncSession,
    phone: str,
    tenant_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    sender_type: str = "customer",
) -> Conversation:
    """Get active conversation or create a new one."""
    query = (
        select(Conversation)
        .where(
            Conversation.contact_phone == phone,
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.sender_type == sender_type,
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    if tenant_id:
        query = query.where(Conversation.tenant_id == tenant_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            contact_phone=phone,
            contact_id=contact_id,
            tenant_id=tenant_id,
            sender_type=sender_type,
            message_history=[],
            current_step="greeting",
            status=ConversationStatus.ACTIVE,
            consent_verified_at=datetime.now(timezone.utc),
        )
        db.add(conversation)
        await db.flush()

    return conversation
