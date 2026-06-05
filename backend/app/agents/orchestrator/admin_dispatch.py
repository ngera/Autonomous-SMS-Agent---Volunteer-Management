"""Orchestrator — admin SMS command dispatcher.

The Orchestrator's job here is intentionally thin: look at the inbound
admin message, decide which domain agent owns the matched command, and
delegate. It does NOT own any command implementation itself.

Routing order (the dispatch tries each module in turn):
  1. Engagement Agent — CHECKIN/CHECKOUT/CHECKIN ME/CHECKOUT ME/STATUS/
     STOP STATUS/STOP STATUS ALL/APPROVE/REJECT (Phase 3)
  2. Recruiter+Scheduler Agent — RESERVE/CANCEL

If neither matches, returns None and the caller falls through to the
admin LLM tool_use conversation. This is the seam at which the
agent_call_log records which agent handled what — each module emits
its own attribution.

Also hosts the SUPER_ADMIN cross-tenant rejection helper used by
the webhook pipeline (Row 6 Edge E). SUPER_ADMIN rejection is genuinely
orchestrator-scoped (it's a security boundary, not a domain action).
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.engagement import admin_intents as engagement_admin
from app.agents.orchestrator import kpi_summary_intent
from app.agents.recruiter_scheduler import admin_intents as scheduler_admin
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.prompts.conversation import _get_prompt, PROMPT_KEYS

logger = get_logger("orchestrator.admin_dispatch")


async def _prompt(db: AsyncSession, key: str, tenant_id: uuid.UUID | None) -> str:
    return await _get_prompt(
        db,
        key,
        PROMPT_KEYS.get(key, ""),
        tenant_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
    )


async def maybe_handle_admin_command(
    db: AsyncSession,
    *,
    admin: AdminUser,
    message_body: str,
) -> str | None:
    """Try every domain agent's admin command parser in order.

    Returns the SMS reply body if any agent matched, else None
    (caller falls through to the admin LLM tool_use conversation).
    """
    body = (message_body or "")

    # Cross-domain — "summary" / "how are things going" daily-digest
    # recall. Matched ahead of domain agents because it's a fixed
    # natural-language phrasing the LLM doesn't need to parse.
    if kpi_summary_intent.matches_kpi_summary_command(body):
        return await kpi_summary_intent.handle(db, admin=admin, message_body=body)

    # Engagement domain — check-in/check-out/status/STOP STATUS family.
    if engagement_admin.matches_engagement_command(body):
        return await engagement_admin.handle(db, admin=admin, message_body=body)

    # Recruiter+Scheduler domain — RESERVE/CANCEL family.
    if scheduler_admin.matches_scheduler_command(body):
        return await scheduler_admin.handle(db, admin=admin, message_body=body)

    return None


async def super_admin_phone_rejection(
    db: AsyncSession, *, admin: AdminUser
) -> str:
    """Row 6 Edge E — SUPER_ADMIN reply when they text any tenant number.

    Genuinely orchestrator-scoped: SUPER_ADMIN is a platform boundary,
    not a domain action. The rejection itself doesn't belong to
    engagement OR recruiter+scheduler.
    """
    from app.core.config import settings as app_settings

    tpl = await _prompt(
        db, "prompt_admin_super_admin_rejection", admin.tenant_id,
    )
    return tpl.format(admin_panel_url=getattr(app_settings, "admin_panel_url", "/"))


__all__ = [
    "maybe_handle_admin_command",
    "super_admin_phone_rejection",
]
