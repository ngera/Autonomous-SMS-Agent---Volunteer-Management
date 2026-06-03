"""Engagement intent routers — server-side short-circuit before LLM.

Decision #7 pattern: regex match → exec → LLM never sees the message.
Phase 1 implements Row 1 (check-in / check-out). Phase 3 fills in
SWITCH / ALSO. The during-event guard ([start_at - 30min, end_at + 1h])
gates every intent in this module — outside the window, the message
falls through to the routing matrix.

Each handler returns None if the intent doesn't match (caller continues
the pipeline) OR an AgentResponse-style dict with the SMS body to send
back. State mutations happen inside the handler (atomic on the same
DB session).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    EVENT_VOLUNTEER_CHECK_IN,
    EVENT_VOLUNTEER_CHECK_OUT,
)
from app.agents.keywords import (
    CHECKIN_INTENT_REGEX,
    CHECKOUT_INTENT_REGEX,
    normalize_keyword,
)
from app.core.logging import get_logger
from app.models.agent_call_log import AgentCallLog
from app.models.availability import SpecificDateSlot
from app.models.booking import (
    Booking,
    BookingStatus,
    CHECKIN_SOURCE_VOLUNTEER_SMS,
    CHECKIN_SOURCE_VOLUNTEER_SMS_EARLY,
    CHECKOUT_SOURCE_VOLUNTEER_SMS,
)
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.prompts.conversation import PROMPT_KEYS
from app.services.event_context import render_event_context

logger = get_logger("engagement.intents")


# ── Helpers ─────────────────────────────────────────────────────────


async def _resolve_prompt(db: AsyncSession, key: str, tenant_id: uuid.UUID) -> str:
    """Tenant-override-aware prompt resolver."""
    from app.prompts.conversation import _get_prompt

    default = PROMPT_KEYS.get(key, "")
    return await _get_prompt(db, key, default, tenant_id)


async def _find_live_bookings_for_contact(
    db: AsyncSession, contact: Contact
) -> list[tuple[Booking, SpecificDateSlot]]:
    """Return (booking, slot) pairs where the slot is in the live window."""
    from app.services.event_eligibility import _slot_in_live_window

    result = await db.execute(
        select(Booking, SpecificDateSlot)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .where(
            Booking.tenant_id == contact.tenant_id,
            Booking.contact_id == contact.id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    now_utc = datetime.now(timezone.utc)
    return [
        (b, s) for b, s in result.all() if _slot_in_live_window(s, now_utc)
    ]


async def _emit_audit(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    """Append an agent_call_log row for the check-in/out event."""
    log = AgentCallLog(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        turn_id=uuid.uuid4(),
        event_type=event_type,
        # Reasonable defaults for the structured-event fields
        source="engagement",
        destination="engagement",
        decision_reason="intent_router",
        payload=payload,
    )
    db.add(log)
    await db.flush()


def _is_expired(conv: Conversation) -> bool:
    """Treat pending_intent as expired if expires_at <= NOW().

    NOTE (review-pass #12): in-memory only check. Do NOT commit a
    write back to the DB on read — stale rows are harmless metadata
    that gets overwritten by the next pending_intent write.
    """
    expires_at = conv.pending_intent_expires_at
    if expires_at is None:
        return True
    return expires_at <= datetime.now(timezone.utc)


# ── Row 1 — check in ────────────────────────────────────────────────


async def maybe_handle_here_check_in(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Volunteer texts HERE / I'M HERE / ARRIVED / CHECKED IN / AT THE SITE.

    Returns the SMS reply body, OR None if this isn't a check-in intent
    (caller should continue pipeline processing).

    Edge handling (Row 1):
      A. Multiple live bookings → disambiguation prompt + pending_intent.
      B. Already checked in to the matched booking → idempotent ack.
      C. Already checked OUT → re-entry confirmation prompt.
      D. Late check-in → silent accept; admin sees "Late by N min" on run-sheet.
      E. Reply uses prompt_checkin_confirmation with event/service/location/time.
    """
    if not CHECKIN_INTENT_REGEX.search(message_body):
        # Also accept exact "BOTH" / "ALL" / "1" / "2" replies if the
        # conversation has a pending checkin_disambiguation intent.
        if not _has_pending_intent(conversation, "checkin_disambiguation"):
            return None
        return await _handle_checkin_disambiguation_reply(
            db, contact=contact, conversation=conversation, message_body=message_body
        )

    live_pairs = await _find_live_bookings_for_contact(db, contact)
    if not live_pairs:
        # Falls through to routing matrix (Row 2/3/4/5 logic).
        return None

    # Edge A — Multi-booking disambiguation
    if len(live_pairs) > 1:
        return await _start_checkin_disambiguation(
            db, contact=contact, conversation=conversation, pairs=live_pairs
        )

    booking, slot = live_pairs[0]
    return await _apply_checkin(
        db, contact=contact, conversation=conversation, booking=booking, slot=slot
    )


async def _apply_checkin(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    booking: Booking,
    slot: SpecificDateSlot,
) -> str:
    """Apply (or reject) check-in for one booking; return SMS reply."""
    now_utc = datetime.now(timezone.utc)

    # Edge B — already checked in (idempotent)
    if booking.checked_in_at is not None and booking.checked_out_at is None:
        already_tpl = await _resolve_prompt(
            db, "prompt_checkin_already_in", contact.tenant_id
        )
        return already_tpl.format(
            hh_mm=booking.checked_in_at.strftime("%I:%M %p").lstrip("0")
        )

    # Edge C — already checked OUT (needs HERE-AGAIN / BACK confirmation)
    if booking.checked_in_at is not None and booking.checked_out_at is not None:
        return await _start_reentry_confirmation(
            db, contact=contact, conversation=conversation, booking=booking
        )

    # Happy path / Edge D (late check-in) / volunteer_sms_early
    # Determine source based on whether we're before slot.start_at.
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]
    eastern = ZoneInfo("America/New_York")
    slot_start = datetime.combine(slot.date, slot.start_time).replace(tzinfo=eastern)
    if now_utc < slot_start:
        source = CHECKIN_SOURCE_VOLUNTEER_SMS_EARLY
    else:
        source = CHECKIN_SOURCE_VOLUNTEER_SMS

    booking.checked_in_at = now_utc
    booking.checked_in_source = source

    await _emit_audit(
        db,
        tenant_id=contact.tenant_id,
        conversation_id=conversation.id,
        event_type=EVENT_VOLUNTEER_CHECK_IN,
        payload={
            "at": now_utc.isoformat(),
            "source": source,
            "booking_id": str(booking.id),
        },
    )

    # Evict admin LLM cache so admin chats see this check-in within seconds.
    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(contact.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    # Render Edge E reply.
    tpl = await _resolve_prompt(db, "prompt_checkin_confirmation", contact.tenant_id)
    ctx = render_event_context(contact=contact, booking=booking, slot=slot)
    return tpl.format(**ctx)


# ── Disambiguation (Edge A) ─────────────────────────────────────────


def _has_pending_intent(conv: Conversation, intent_type: str) -> bool:
    if conv.pending_intent is None or _is_expired(conv):
        return False
    pi = conv.pending_intent
    return isinstance(pi, dict) and pi.get("intent_type") == intent_type


async def _start_checkin_disambiguation(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    pairs: list[tuple[Booking, SpecificDateSlot]],
) -> str:
    """Set pending_intent and render the disambiguation picker."""
    booking_ids = [str(b.id) for b, _ in pairs]
    # TTL = max(slot.end_at + 1h) across offered bookings, in UTC.
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]
    eastern = ZoneInfo("America/New_York")
    max_expiry = datetime.now(timezone.utc)
    for _, slot in pairs:
        end_at = datetime.combine(slot.date, slot.end_time).replace(tzinfo=eastern)
        candidate = end_at + timedelta(hours=1)
        if candidate > max_expiry:
            max_expiry = candidate

    conversation.pending_intent = {
        "intent_type": "checkin_disambiguation",
        "booking_ids": booking_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    conversation.pending_intent_expires_at = max_expiry

    # BOTH for exactly 2, ALL for 3+ (review-pass F3 + last fix-pass #3).
    all_keyword = "BOTH" if len(pairs) == 2 else "ALL"
    valid_options = ", ".join(str(i + 1) for i in range(len(pairs)))
    valid_options = f"{valid_options}, or {all_keyword}"

    numbered_lines = []
    for i, (booking, slot) in enumerate(pairs, 1):
        start = slot.start_time.strftime("%I:%M %p").lstrip("0")
        end = slot.end_time.strftime("%I:%M %p").lstrip("0")
        name = slot.label or "(unnamed event)"
        numbered_lines.append(f"{i}) {name}, {start}-{end}")
    numbered_list = "\n".join(numbered_lines)

    tpl = await _resolve_prompt(db, "prompt_checkin_disambiguation", contact.tenant_id)
    return tpl.format(
        count=len(pairs), numbered_list=numbered_list, valid_options=valid_options
    )


async def _handle_checkin_disambiguation_reply(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Handle volunteer's 1 / 2 / BOTH / ALL reply."""
    pi = conversation.pending_intent or {}
    booking_ids: list[str] = list(pi.get("booking_ids") or [])
    if not booking_ids:
        return None

    upper = normalize_keyword(message_body)

    selected_ids: list[str] = []
    if upper in {"BOTH", "ALL"}:
        selected_ids = booking_ids
    else:
        try:
            idx = int(upper)
        except ValueError:
            # Non-matching reply — clear pending and fall through.
            conversation.pending_intent = None
            conversation.pending_intent_expires_at = None
            return None
        if not (1 <= idx <= len(booking_ids)):
            conversation.pending_intent = None
            conversation.pending_intent_expires_at = None
            return None
        selected_ids = [booking_ids[idx - 1]]

    # Apply check-in to each selected booking; concatenate replies.
    replies = []
    for bid in selected_ids:
        b_result = await db.execute(
            select(Booking, SpecificDateSlot)
            .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
            .where(Booking.id == uuid.UUID(bid))
        )
        row = b_result.first()
        if row is None:
            continue
        booking, slot = row
        reply = await _apply_checkin(
            db, contact=contact, conversation=conversation, booking=booking, slot=slot
        )
        replies.append(reply)

    # Clear pending state.
    conversation.pending_intent = None
    conversation.pending_intent_expires_at = None

    return "\n\n".join(replies) if replies else None


# ── Re-entry confirmation (Edge C) ──────────────────────────────────


async def _start_reentry_confirmation(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    booking: Booking,
) -> str:
    """Set pending checkout_reentry_confirmation; ask for HERE-AGAIN / BACK."""
    conversation.pending_intent = {
        "intent_type": "checkout_reentry_confirmation",
        "booking_id": str(booking.id),
        "prior_checked_out_at": booking.checked_out_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    conversation.pending_intent_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=30
    )
    tpl = await _resolve_prompt(db, "prompt_checkin_reentry_prompt", contact.tenant_id)
    return tpl.format(
        hh_mm=booking.checked_out_at.strftime("%I:%M %p").lstrip("0")
    )


async def maybe_handle_reentry(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Volunteer texts HERE-AGAIN or BACK after being asked to re-enter."""
    if not _has_pending_intent(conversation, "checkout_reentry_confirmation"):
        return None
    upper = normalize_keyword(message_body)
    if upper not in {"HERE-AGAIN", "BACK"}:
        return None

    pi = conversation.pending_intent or {}
    booking_id = pi.get("booking_id")
    if not booking_id:
        return None

    result = await db.execute(
        select(Booking, SpecificDateSlot)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .where(Booking.id == uuid.UUID(booking_id))
    )
    row = result.first()
    if row is None:
        return None
    booking, slot = row

    now_utc = datetime.now(timezone.utc)
    # Log the old checkout to audit before clearing it.
    if booking.checked_out_at is not None:
        await _emit_audit(
            db,
            tenant_id=contact.tenant_id,
            conversation_id=conversation.id,
            event_type=EVENT_VOLUNTEER_CHECK_OUT,
            payload={
                "at": booking.checked_out_at.isoformat(),
                "source": booking.checked_out_source or "unknown",
                "booking_id": str(booking.id),
            },
        )
    booking.checked_out_at = None
    booking.checked_out_source = None
    booking.checked_in_at = now_utc
    booking.checked_in_source = CHECKIN_SOURCE_VOLUNTEER_SMS

    await _emit_audit(
        db,
        tenant_id=contact.tenant_id,
        conversation_id=conversation.id,
        event_type=EVENT_VOLUNTEER_CHECK_IN,
        payload={
            "at": now_utc.isoformat(),
            "source": CHECKIN_SOURCE_VOLUNTEER_SMS,
            "booking_id": str(booking.id),
            "reentry": True,
        },
    )

    conversation.pending_intent = None
    conversation.pending_intent_expires_at = None

    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(contact.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    tpl = await _resolve_prompt(
        db, "prompt_checkin_reentry_confirmation", contact.tenant_id
    )
    ctx = render_event_context(contact=contact, booking=booking, slot=slot)
    return tpl.format(**ctx)


# ── Row 1 — check out ───────────────────────────────────────────────


async def maybe_handle_check_out(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Volunteer texts DONE / LEAVING / FINISHED / CHECKING OUT / HEADING OUT.

    Marks the current segment closed. Hours derivation (multi-segment)
    is reconstructed at review-creation time (Phase 4); during-event we
    just stamp checked_out_at on the current row (decision #10).
    """
    if not CHECKOUT_INTENT_REGEX.search(message_body):
        return None

    live_pairs = await _find_live_bookings_for_contact(db, contact)
    # For check-out, restrict to bookings that have been checked in.
    candidates = [
        (b, s) for b, s in live_pairs
        if b.checked_in_at is not None and b.checked_out_at is None
    ]
    if not candidates:
        return None

    # If multiple, close them all (the volunteer is leaving everything).
    now_utc = datetime.now(timezone.utc)
    closed = []
    for booking, slot in candidates:
        booking.checked_out_at = now_utc
        booking.checked_out_source = CHECKOUT_SOURCE_VOLUNTEER_SMS
        await _emit_audit(
            db,
            tenant_id=contact.tenant_id,
            conversation_id=conversation.id,
            event_type=EVENT_VOLUNTEER_CHECK_OUT,
            payload={
                "at": now_utc.isoformat(),
                "source": CHECKOUT_SOURCE_VOLUNTEER_SMS,
                "booking_id": str(booking.id),
            },
        )
        closed.append((booking, slot))

    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(contact.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    tpl = await _resolve_prompt(db, "prompt_checkout_confirmation", contact.tenant_id)

    # Compute total hours for the segment that just closed (single segment for now).
    parts = []
    for booking, slot in closed:
        total = None
        if booking.checked_in_at and booking.checked_out_at:
            delta = booking.checked_out_at - booking.checked_in_at
            total = round(delta.total_seconds() / 3600, 2)
        ctx = render_event_context(
            contact=contact, booking=booking, slot=slot, total_hours=total
        )
        parts.append(tpl.format(**ctx))
    return "\n\n".join(parts)


# ── Row 1 — service switch / add (Phase 3) ──────────────────────────

# Regex patterns for SWITCH/ALSO intents. Conservative on the verb
# placement so casual phrases like "I want to switch to cooking" still
# match. The (.+?) capture group is greedy enough to grab multi-word
# service names like "Setup Crew".
RE_SWITCH = re.compile(
    r"\b(?:switch(?:\s+to)?|moving\s+to|changing\s+to)\s+(.+)$",
    re.IGNORECASE,
)
RE_ALSO = re.compile(
    r"\b(?:also(?:\s+doing)?|additionally|and(?:\s+also)?)\s+(.+)$",
    re.IGNORECASE,
)


async def _find_current_pair(
    db: AsyncSession, contact: Contact
) -> tuple[object, object] | None:
    """Helper: pick a single live booking+slot for SWITCH/ALSO. If
    multiple, returns None (caller falls back to LLM since these intents
    rely on an unambiguous current booking).
    """
    pairs = await _find_live_bookings_for_contact(db, contact)
    if len(pairs) == 1:
        return pairs[0]
    return None


async def maybe_handle_service_switch(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Volunteer texts SWITCH cooking / MOVING TO setup / CHANGING TO cleanup.

    Creates a pending booking_service_log entry. Decision #17 — if a
    prior pending row exists for this booking, it's marked superseded.
    Admin notification fires.
    """
    m = RE_SWITCH.search(message_body or "")
    if not m:
        return None

    pair = await _find_current_pair(db, contact)
    if pair is None:
        return None
    booking, slot = pair

    from app.prompts.conversation import PROMPT_KEYS
    from app.services.service_log import (
        create_pending_entry,
        resolve_service_name,
    )

    service_text = m.group(1).strip().rstrip(".!?")
    appt_type = await resolve_service_name(
        db, tenant_id=contact.tenant_id, slot=slot, name_query=service_text
    )
    if appt_type is None:
        tpl = await _resolve_prompt(
            db, "prompt_service_unrecognized", contact.tenant_id
        )
        return tpl.format(
            service_attempted=service_text,
            event_name=slot.label or "your event",
        )

    await create_pending_entry(
        db,
        booking=booking,
        slot=slot,
        appointment_type=appt_type,
        contact=contact,
        is_switch=True,
    )

    tpl = await _resolve_prompt(
        db, "prompt_service_switch_pending", contact.tenant_id
    )
    ctx = render_event_context(
        contact=contact, booking=booking, slot=slot, appointment_type=appt_type
    )
    return tpl.format(**ctx)


async def maybe_handle_service_add(
    db: AsyncSession,
    *,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Volunteer texts ALSO setup / ADDITIONALLY cleanup / AND ALSO cooking.

    Creates a pending booking_service_log entry alongside the existing
    one (no supersede).
    """
    m = RE_ALSO.search(message_body or "")
    if not m:
        return None

    pair = await _find_current_pair(db, contact)
    if pair is None:
        return None
    booking, slot = pair

    from app.prompts.conversation import PROMPT_KEYS
    from app.services.service_log import (
        create_pending_entry,
        resolve_service_name,
    )

    service_text = m.group(1).strip().rstrip(".!?")
    appt_type = await resolve_service_name(
        db, tenant_id=contact.tenant_id, slot=slot, name_query=service_text
    )
    if appt_type is None:
        tpl = await _resolve_prompt(
            db, "prompt_service_unrecognized", contact.tenant_id
        )
        return tpl.format(
            service_attempted=service_text,
            event_name=slot.label or "your event",
        )

    await create_pending_entry(
        db,
        booking=booking,
        slot=slot,
        appointment_type=appt_type,
        contact=contact,
        is_switch=False,
    )

    tpl = await _resolve_prompt(
        db, "prompt_service_add_pending", contact.tenant_id
    )
    ctx = render_event_context(
        contact=contact, booking=booking, slot=slot, appointment_type=appt_type
    )
    return tpl.format(**ctx)


__all__ = [
    "maybe_handle_here_check_in",
    "maybe_handle_check_out",
    "maybe_handle_reentry",
    "maybe_handle_service_switch",
    "maybe_handle_service_add",
]
