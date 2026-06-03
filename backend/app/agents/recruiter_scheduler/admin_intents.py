"""Recruiter+Scheduler Agent — admin-side SMS intents.

This module owns admin commands that operate on the
*pre-event scheduling and booking-creation domain*:
  - RESERVE [<event>] [| <service>]    — admin self-reservation (Phase 1)
                                          two-stage parser (Phase 3 full)

agent_call_log attribution: source/destination = AGENT_RECRUITER_SCHEDULER.

Phase 1 ships a minimal RESERVE matcher that defers heavy work to
Phase 3 (multi-stage picker + pending_intent state). For now, calling
RESERVE replies with usage help so the command isn't a silent no-op.

The Orchestrator dispatcher (admin_dispatch.py) routes admin messages
matching the RESERVE family to this module.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.prompts.conversation import _get_prompt, PROMPT_KEYS

logger = get_logger("recruiter_scheduler.admin_intents")


# ── Command regex (recruiter+scheduler-domain only) ─────────────────

RE_RESERVE = re.compile(r"^\s*RESERVE(?:\s+(.+))?\s*$", re.IGNORECASE)
RE_CANCEL = re.compile(r"^\s*CANCEL\s*$", re.IGNORECASE)


def matches_scheduler_command(body: str) -> bool:
    """Quick check used by the Orchestrator dispatcher."""
    b = body or ""
    return bool(RE_RESERVE.match(b) or RE_CANCEL.match(b))


async def _prompt(db: AsyncSession, key: str, tenant_id: uuid.UUID) -> str:
    return await _get_prompt(db, key, PROMPT_KEYS.get(key, ""), tenant_id)


# ── Public entrypoint ──────────────────────────────────────────────


async def handle(
    db: AsyncSession,
    *,
    admin: AdminUser,
    message_body: str,
) -> str | None:
    """Try every scheduler-domain admin command in priority order.

    Phase 1 returns a friendly placeholder for RESERVE. Phase 3 will
    fill in the 2-stage event/service picker, capacity check (SELECT
    FOR UPDATE per decision #29a), and the prompt_admin_reserve_*
    template family.
    """
    body = (message_body or "").strip()

    # CANCEL — clears pending_intent (RESERVE picker, walk-up picker, etc.)
    if RE_CANCEL.match(body):
        # Phase 1: simplest implementation — find the conversation and
        # null out pending_intent if any. Pending_intent is tied to a
        # conversation, but admin messages don't always create one. For
        # now reply that there's nothing to cancel.
        return "Nothing to cancel right now."

    # RESERVE — Phase 1 stub. Phase 3 fills the multi-stage flow.
    m = RE_RESERVE.match(body)
    if m:
        # If the admin supplied an event guess, we acknowledge it.
        args = (m.group(1) or "").strip()
        if args:
            return (
                f"RESERVE picked up '{args}'. Reservation flow ships in "
                "Phase 3 — please use the admin UI to reserve yourself for "
                "an event for now."
            )
        return (
            "RESERVE coming in Phase 3 — please use the admin UI to "
            "reserve yourself for an event for now."
        )

    return None


__all__ = [
    "handle",
    "matches_scheduler_command",
]
