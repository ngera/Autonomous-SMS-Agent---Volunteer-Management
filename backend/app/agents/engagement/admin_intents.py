"""Engagement Agent — admin-side SMS intents (Phase 1 + Phase 2).

This module owns the admin commands that operate on the
*post-signup engagement lifecycle*:
  - CHECKIN / CHECKOUT <name>             — admin marks attendance
  - CHECKIN ME / CHECKOUT ME              — admin self-action shortcut
  - STATUS [<event>]                      — roster summary
  - STOP STATUS / STOP STATUS ALL         — silence auto-pings
  - APPROVE / REJECT <name>               — Phase 3 service-log dispositions
    (stubs reserved; Phase 3 fills the handler)

Pairs with the volunteer-side intents in
[app/agents/engagement/intents.py](backend/app/agents/engagement/intents.py)
so the full engagement domain lives in one folder. The Orchestrator's
admin_dispatch.py decides which agent's admin_intents module to call
based on the regex match; this module owns the implementation for
engagement-domain commands.

agent_call_log attribution: `source="engagement"`, `destination="engagement"`.

Decision references:
  - Row 6 Edge A: admin commands always win.
  - Row 6 Edge B: name-not-found → reject; don't silently create.
  - Row 6 Edge C: bare CHECKIN/CHECKOUT defaults to self if admin
    has a personal Booking, else usage help.
  - #31: emits agent_call_log EVENT_ADMIN_OVERRIDE for each mutation.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AGENT_ENGAGEMENT, EVENT_ADMIN_OVERRIDE
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.agent_call_log import AgentCallLog
from app.models.availability import SpecificDateSlot
from app.models.booking import (
    Booking,
    BookingStatus,
    CHECKIN_SOURCE_ADMIN_OVERRIDE,
    CHECKOUT_SOURCE_ADMIN_OVERRIDE,
)
from app.models.contact import Contact
from app.prompts.conversation import _get_prompt, PROMPT_KEYS
from app.services.event_eligibility import _slot_in_live_window

logger = get_logger("engagement.admin_intents")


# ── Command regex (engagement-domain only) ──────────────────────────

RE_CHECKIN_ME = re.compile(r"^\s*CHECKIN\s+ME\s*$", re.IGNORECASE)
RE_CHECKOUT_ME = re.compile(r"^\s*CHECKOUT\s+ME\s*$", re.IGNORECASE)
RE_CHECKIN = re.compile(r"^\s*CHECKIN\s+(.+?)\s*$", re.IGNORECASE)
RE_CHECKOUT = re.compile(r"^\s*CHECKOUT\s+(.+?)\s*$", re.IGNORECASE)
RE_BARE_CHECKIN = re.compile(r"^\s*CHECKIN\s*$", re.IGNORECASE)
RE_BARE_CHECKOUT = re.compile(r"^\s*CHECKOUT\s*$", re.IGNORECASE)
RE_STATUS = re.compile(r"^\s*STATUS(?:\s+(.+?))?\s*$", re.IGNORECASE)
RE_STOP_STATUS_ALL = re.compile(r"^\s*STOP\s+STATUS\s+ALL\s*$", re.IGNORECASE)
RE_STOP_STATUS = re.compile(r"^\s*STOP\s+STATUS\s*$", re.IGNORECASE)
# Phase 3 — service-log dispositions
RE_APPROVE = re.compile(r"^\s*APPROVE\s+(.+?)\s*$", re.IGNORECASE)
RE_REJECT = re.compile(r"^\s*REJECT\s+(.+?)\s*$", re.IGNORECASE)


def matches_engagement_command(body: str) -> bool:
    """Quick check used by the Orchestrator dispatcher to decide whether
    to route an admin message into this module.
    """
    b = body or ""
    return bool(
        RE_CHECKIN_ME.match(b)
        or RE_CHECKOUT_ME.match(b)
        or RE_CHECKIN.match(b)
        or RE_CHECKOUT.match(b)
        or RE_BARE_CHECKIN.match(b)
        or RE_BARE_CHECKOUT.match(b)
        or RE_STATUS.match(b)
        or RE_STOP_STATUS.match(b)
        or RE_STOP_STATUS_ALL.match(b)
        or RE_APPROVE.match(b)
        or RE_REJECT.match(b)
    )


# ── Helpers ─────────────────────────────────────────────────────────


async def _prompt(db: AsyncSession, key: str, tenant_id: uuid.UUID) -> str:
    return await _get_prompt(db, key, PROMPT_KEYS.get(key, ""), tenant_id)


async def _admin_linked_contact(db: AsyncSession, admin: AdminUser) -> Contact | None:
    result = await db.execute(
        select(Contact).where(Contact.admin_user_id == admin.id)
    )
    return result.scalar_one_or_none()


async def _admin_personal_live_bookings(
    db: AsyncSession, admin: AdminUser
) -> list[tuple[Booking, SpecificDateSlot]]:
    contact = await _admin_linked_contact(db, admin)
    if contact is None:
        return []
    result = await db.execute(
        select(Booking, SpecificDateSlot)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .where(
            Booking.tenant_id == admin.tenant_id,
            Booking.contact_id == contact.id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    now_utc = datetime.now(timezone.utc)
    return [(b, s) for b, s in result.all() if _slot_in_live_window(s, now_utc)]


async def _fuzzy_resolve_contact(
    db: AsyncSession, tenant_id: uuid.UUID, query: str
) -> list[Contact]:
    """Fuzzy match a Contact by last-name / prefix / phone for tenant."""
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    result = await db.execute(
        select(Contact)
        .where(
            Contact.tenant_id == tenant_id,
            (Contact.name.ilike(like)) | (Contact.phone.ilike(like)),
        )
        .limit(6)
    )
    return list(result.scalars().all())


async def _emit_admin_override(
    db: AsyncSession,
    *,
    admin: AdminUser,
    target_table: str,
    target_id: uuid.UUID,
    field: str,
    prior_value: Any,
    new_value: Any,
) -> None:
    """Emit agent_call_log row for an admin override mutation.

    source/destination = AGENT_ENGAGEMENT — this is the engagement
    domain's audit trail, NOT the orchestrator's. Phase 5 observability
    queries that pivot on agent-source will see the correct attribution.
    """
    db.add(
        AgentCallLog(
            tenant_id=admin.tenant_id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_ADMIN_OVERRIDE,
            source=AGENT_ENGAGEMENT,
            destination=AGENT_ENGAGEMENT,
            decision_reason="admin_sms_command",
            payload={
                "target_table": target_table,
                "target_id": str(target_id),
                "field": field,
                "prior_value": str(prior_value) if prior_value is not None else None,
                "new_value": str(new_value) if new_value is not None else None,
                "admin_user_id": str(admin.id),
            },
        )
    )


# ── Command handlers ───────────────────────────────────────────────


async def _apply_admin_checkin(
    db: AsyncSession,
    *,
    admin: AdminUser,
    booking: Booking,
    slot: SpecificDateSlot,
) -> str:
    now_utc = datetime.now(timezone.utc)
    prior = booking.checked_in_at
    booking.checked_in_at = now_utc
    booking.checked_in_by_id = admin.id
    booking.checked_in_source = CHECKIN_SOURCE_ADMIN_OVERRIDE
    await _emit_admin_override(
        db,
        admin=admin,
        target_table="bookings",
        target_id=booking.id,
        field="checked_in_at",
        prior_value=prior,
        new_value=now_utc,
    )

    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(admin.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    tpl = await _prompt(db, "prompt_admin_checkin_success", admin.tenant_id)
    contact_result = await db.execute(
        select(Contact).where(Contact.id == booking.contact_id)
    )
    contact = contact_result.scalar_one()
    return tpl.format(
        volunteer_name=contact.name or "(unnamed)",
        event_name=slot.label or "(unnamed event)",
        hh_mm=now_utc.strftime("%I:%M %p").lstrip("0"),
    )


async def _apply_admin_checkout(
    db: AsyncSession,
    *,
    admin: AdminUser,
    booking: Booking,
    slot: SpecificDateSlot,
) -> str:
    now_utc = datetime.now(timezone.utc)
    prior = booking.checked_out_at
    booking.checked_out_at = now_utc
    booking.checked_out_by_id = admin.id
    booking.checked_out_source = CHECKOUT_SOURCE_ADMIN_OVERRIDE
    await _emit_admin_override(
        db,
        admin=admin,
        target_table="bookings",
        target_id=booking.id,
        field="checked_out_at",
        prior_value=prior,
        new_value=now_utc,
    )

    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(admin.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    tpl = await _prompt(db, "prompt_admin_checkout_success", admin.tenant_id)
    contact_result = await db.execute(
        select(Contact).where(Contact.id == booking.contact_id)
    )
    contact = contact_result.scalar_one()
    return tpl.format(
        volunteer_name=contact.name or "(unnamed)",
        event_name=slot.label or "(unnamed event)",
        hh_mm=now_utc.strftime("%I:%M %p").lstrip("0"),
    )


async def _self_action(
    db: AsyncSession,
    *,
    admin: AdminUser,
    direction: str,  # 'in' or 'out'
) -> str | None:
    """Apply CHECKIN ME / CHECKOUT ME for the admin's linked Contact.

    Returns None if admin has no personal Booking in live window;
    caller falls through to usage-help reply.
    """
    pairs = await _admin_personal_live_bookings(db, admin)
    if direction == "in":
        targets = [(b, s) for b, s in pairs if b.checked_in_at is None]
    else:
        targets = [
            (b, s)
            for b, s in pairs
            if b.checked_in_at is not None and b.checked_out_at is None
        ]
    if not targets:
        return None
    targets.sort(key=lambda bs: (bs[1].date, bs[1].start_time))
    booking, slot = targets[0]
    if direction == "in":
        return await _apply_admin_checkin(db, admin=admin, booking=booking, slot=slot)
    return await _apply_admin_checkout(db, admin=admin, booking=booking, slot=slot)


async def _find_booking_by_name_in_live_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name_query: str,
) -> tuple[Booking, SpecificDateSlot, Contact] | str:
    """Resolve a name to a Booking in a live event."""
    candidates = await _fuzzy_resolve_contact(db, tenant_id, name_query)
    if not candidates:
        return ""
    matches: list[tuple[Booking, SpecificDateSlot, Contact]] = []
    now_utc = datetime.now(timezone.utc)
    for contact in candidates:
        result = await db.execute(
            select(Booking, SpecificDateSlot)
            .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
            .where(
                Booking.contact_id == contact.id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
        for b, s in result.all():
            if _slot_in_live_window(s, now_utc):
                matches.append((b, s, contact))
                break
    if not matches:
        return ""
    if len(matches) == 1:
        return matches[0]
    tpl = await _prompt(db, "prompt_admin_command_disambiguation", tenant_id)
    numbered = "\n".join(
        f"{i + 1}) {c.name or '(unnamed)'} ({c.phone})"
        for i, (_, _, c) in enumerate(matches)
    )
    valid = ", ".join(str(i + 1) for i in range(len(matches)))
    return tpl.format(
        name_attempted=name_query, numbered_list=numbered, valid_options=valid
    )


# ── Phase 3 APPROVE / REJECT handler ───────────────────────────────


async def _handle_approve_reject(
    db: AsyncSession,
    *,
    admin: AdminUser,
    name_query: str,
    approve: bool,
) -> str:
    """Resolve volunteer name → latest pending service_log entry → flip
    status with optimistic-version write (decision #29b). On race,
    reply with "stale" message so admin can retry.
    """
    from app.services.service_log import (
        OptimisticLockError,
        approve_pending,
        find_latest_pending_for_volunteer_name,
        reject_pending,
    )

    found = await find_latest_pending_for_volunteer_name(
        db, tenant_id=admin.tenant_id, name_query=name_query
    )
    if found is None:
        tpl = await _prompt(
            db, "prompt_admin_command_name_not_found", admin.tenant_id
        )
        return tpl.format(
            name_attempted=name_query,
            event_name="any pending service requests",
        )

    entry, contact, slot, appt = found
    try:
        if approve:
            await approve_pending(
                db,
                entry_id=entry.id,
                expected_version=entry.version,
                admin=admin,
            )
        else:
            await reject_pending(
                db,
                entry_id=entry.id,
                expected_version=entry.version,
                admin=admin,
                reason="rejected_via_sms",
            )
    except OptimisticLockError:
        return (
            f"Couldn't {('approve' if approve else 'reject')} — "
            f"{contact.name or contact.phone}'s request was changed "
            "since you opened it. Try the run-sheet UI for the latest."
        )

    tpl_key = "prompt_admin_service_approval_done"
    tpl = await _prompt(db, tpl_key, admin.tenant_id)
    return tpl


# ── Public entrypoint ──────────────────────────────────────────────


async def handle(
    db: AsyncSession,
    *,
    admin: AdminUser,
    message_body: str,
) -> str | None:
    """Try every engagement-domain admin command in priority order.

    Returns SMS reply body on hit, None on miss (caller continues
    dispatching to other agents).
    """
    body = (message_body or "").strip()

    # CHECKIN ME / CHECKOUT ME
    if RE_CHECKIN_ME.match(body):
        reply = await _self_action(db, admin=admin, direction="in")
        if reply is not None:
            return reply
        return await _prompt(db, "prompt_admin_command_usage_help", admin.tenant_id)
    if RE_CHECKOUT_ME.match(body):
        reply = await _self_action(db, admin=admin, direction="out")
        if reply is not None:
            return reply
        return await _prompt(db, "prompt_admin_command_usage_help", admin.tenant_id)

    # Bare CHECKIN / CHECKOUT — default to self per Row 6 Edge C
    if RE_BARE_CHECKIN.match(body):
        reply = await _self_action(db, admin=admin, direction="in")
        if reply is not None:
            return reply
        return await _prompt(db, "prompt_admin_command_usage_help", admin.tenant_id)
    if RE_BARE_CHECKOUT.match(body):
        reply = await _self_action(db, admin=admin, direction="out")
        if reply is not None:
            return reply
        return await _prompt(db, "prompt_admin_command_usage_help", admin.tenant_id)

    # Named CHECKIN / CHECKOUT
    m_in = RE_CHECKIN.match(body)
    if m_in:
        result = await _find_booking_by_name_in_live_event(
            db, tenant_id=admin.tenant_id, name_query=m_in.group(1)
        )
        if isinstance(result, str):
            if not result:
                tpl = await _prompt(
                    db, "prompt_admin_command_name_not_found", admin.tenant_id
                )
                return tpl.format(
                    name_attempted=m_in.group(1), event_name="any live event"
                )
            return result
        booking, slot, _ = result
        return await _apply_admin_checkin(db, admin=admin, booking=booking, slot=slot)

    m_out = RE_CHECKOUT.match(body)
    if m_out:
        result = await _find_booking_by_name_in_live_event(
            db, tenant_id=admin.tenant_id, name_query=m_out.group(1)
        )
        if isinstance(result, str):
            if not result:
                tpl = await _prompt(
                    db, "prompt_admin_command_name_not_found", admin.tenant_id
                )
                return tpl.format(
                    name_attempted=m_out.group(1), event_name="any live event"
                )
            return result
        booking, slot, _ = result
        return await _apply_admin_checkout(db, admin=admin, booking=booking, slot=slot)

    # STOP STATUS ALL — global opt-out
    if RE_STOP_STATUS_ALL.match(body):
        from app.services.event_status_ping import silence_admin_globally
        await silence_admin_globally(db, admin_user_id=admin.id)
        return (
            "Status pings disabled globally. A super-admin can re-enable "
            "from your admin profile."
        )

    # STOP STATUS — silence the admin's most-recent live event
    if RE_STOP_STATUS.match(body):
        from app.agents.orchestrator.admin_prompt_blocks import (
            _query_live_slots_with_counts,
        )
        from app.services.event_status_ping import silence_admin_for_slot

        live = await _query_live_slots_with_counts(db, admin.tenant_id)
        if not live:
            return "No live events right now — nothing to silence."
        live.sort(key=lambda r: (r[0].date, r[0].start_time), reverse=True)
        slot, _, _ = live[0]
        await silence_admin_for_slot(
            db,
            tenant_id=admin.tenant_id,
            admin_user_id=admin.id,
            slot_id=slot.id,
        )
        return f"Status pings silenced for {slot.label or 'this event'}."

    # APPROVE / REJECT <name> — Phase 3 service-log dispositions
    m_approve = RE_APPROVE.match(body)
    if m_approve:
        return await _handle_approve_reject(
            db, admin=admin, name_query=m_approve.group(1), approve=True
        )
    m_reject = RE_REJECT.match(body)
    if m_reject:
        return await _handle_approve_reject(
            db, admin=admin, name_query=m_reject.group(1), approve=False
        )

    # STATUS [<event>]
    m_status = RE_STATUS.match(body)
    if m_status:
        from app.agents.orchestrator.admin_prompt_blocks import (
            _query_live_slots_with_counts,
        )

        event_ref = m_status.group(1)
        rows = await _query_live_slots_with_counts(db, admin.tenant_id)
        if not rows:
            return "No live events right now."

        if event_ref:
            ref_l = event_ref.lower()
            rows = [
                r for r in rows
                if (r[0].label or "").lower().find(ref_l) >= 0
            ] or rows

        rows.sort(key=lambda r: (r[0].date, r[0].start_time), reverse=True)
        slot, checked_in, total = rows[0]
        missing = total - checked_in
        missing_str = f"{missing} not yet checked in" if missing > 0 else "none"
        tpl = await _prompt(db, "prompt_roster_status_ping", admin.tenant_id)
        return tpl.format(
            event_name=slot.label or "(unnamed event)",
            checked_in_count=checked_in,
            total_count=total,
            missing_names_capped=missing_str,
            link="/run-sheet",
        )

    return None


__all__ = [
    "handle",
    "matches_engagement_command",
]
