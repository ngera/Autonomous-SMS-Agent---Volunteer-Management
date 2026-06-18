"""Chat-tool handlers for the Recruitment Agent.

These handlers plug into the existing admin tool-use loop (registered in
``tool_handlers.TOOL_HANDLERS``) so the admin can drive recruitment from
SMS or the admin test-tool UI.

- ``start_recruitment_campaign`` — creates the draft campaign and kicks
  off the planner as a background-style task (we schedule it via asyncio
  so we don't block the SMS response).
- ``approve_recruitment_campaign`` — flips the most recent
  ``awaiting_approval`` campaign for this tenant to ``active`` and
  materializes wave rows.
- ``recruitment_status`` — short status snapshot for the admin.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import desc, select

# `executor` and `planner` are imported lazily inside the functions that
# need them. They both pull in `app.modules.tool_executor` -> `tool_handlers`,
# and tool_handlers in turn imports from this module at module-bottom to
# register handlers. The cycle resolves at runtime in the live app boot,
# but cold imports (e.g. from the eval framework) hit a partial-init error.
# Lazy imports inside callers break the cycle without behavior change.
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.availability import SpecificDateSlot
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)
from app.models.tenant import Tenant

# ToolContext is imported only for type annotations. With
# `from __future__ import annotations` (above) all annotations are
# strings at runtime, so we can defer this to TYPE_CHECKING and break
# the chat_tools <-> tool_handlers import cycle. The cycle resolves at
# runtime in the live app, but cold imports (e.g. from the eval
# framework) hit a partial-init error otherwise.
if TYPE_CHECKING:
    from app.modules.tool_handlers import ToolContext

logger = get_logger("recruiter.chat_tools")

# Module-level set of in-flight planner tasks. asyncio.create_task only
# returns a *weakly-referenced* Task; if no strong reference is held the
# Python GC can collect it before it runs. Without this set, the planner
# silently never executed and campaigns stayed in DRAFT forever.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _schedule_background(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    task.add_done_callback(_log_background_task_result)


def _log_background_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        logger.warning("Background task was cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "Background task raised: %s", exc, exc_info=(type(exc), exc, exc.__traceback__)
        )


async def _kick_off_planner_task(
    campaign_id: uuid.UUID,
    admin_phone: str | None,
    admin_user_id: uuid.UUID | None = None,
) -> None:
    """Background task: run planner, then notify the admin.

    Notification is two-pronged:
    - **AdminNotification row** (always written, regardless of phone or
      mode). The dashboard's Notifications panel surfaces it. This is the
      reliable channel.
    - **SMS** (only when ``admin_phone`` is a real phone). Skipped if
      admin has no phone configured — the in-app notification still fires.

    Without this fan-out, an admin without a phone would get nothing back
    after planning and would have to discover the awaiting_approval
    campaign by browsing the Campaigns page.
    """
    from app.agents.recruiter import executor, planner

    logger.info(
        "Planner task starting for campaign %s (admin_phone=%s)",
        campaign_id, admin_phone,
    )
    try:
        summary = await planner.run_planner(campaign_id)
    except Exception:
        logger.exception(
            "Planner raised for campaign %s", campaign_id
        )
        summary = None

    logger.info(
        "Planner task finished for campaign %s (summary=%s chars)",
        campaign_id, len(summary or ""),
    )

    async with async_session_factory() as db:
        campaign = await db.get(RecruitmentCampaign, campaign_id)
        if not campaign:
            logger.warning(
                "Campaign %s missing post-planner; nothing to notify",
                campaign_id,
            )
            return
        tenant = await db.get(Tenant, campaign.tenant_id)
        if not tenant:
            return
        slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
        event_label = slot.label if slot and slot.label else "event"
        event_date = slot.date.isoformat() if slot else ""

        # 1) ALWAYS create an in-app notification (success or error).
        from app.models.notification import NotificationType
        from app.services.notification import create_notification
        try:
            if summary:
                await create_notification(
                    db=db,
                    notification_type=NotificationType.RECRUITMENT_PLAN_READY,
                    title=f"Recruitment plan ready: {event_label}"
                    + (f" ({event_date})" if event_date else ""),
                    body=(
                        f"{summary}\n\n"
                        "Approve from the Campaigns page or reply APPROVE "
                        "by SMS."
                    ),
                    tenant_id=tenant.id,
                    admin_user_id=admin_user_id or campaign.created_by_admin_id,
                    reference_id=campaign.id,
                    reference_type="recruitment_campaign",
                )
            else:
                await create_notification(
                    db=db,
                    notification_type=NotificationType.RECRUITMENT_PLAN_FAILED,
                    title=f"Recruitment planning failed: {event_label}",
                    body=(
                        "The planner couldn't produce a plan. Open the "
                        "campaign on the Campaigns page to retry."
                    ),
                    tenant_id=tenant.id,
                    admin_user_id=admin_user_id or campaign.created_by_admin_id,
                    reference_id=campaign.id,
                    reference_type="recruitment_campaign",
                )
        except Exception:
            logger.exception(
                "Failed to create planning notification for campaign %s",
                campaign.id,
            )

        # 2) Always mirror the plan into the admin's sender_type='admin'
        #    conversation so the multi-volunteer test page can show it.
        #    Use the admin's real phone if set; otherwise fall back to the
        #    test phone (+10000000000), which is what test_conversation
        #    uses for admin-mode chats.
        #
        #    When SMS is suppressed (settings.sms_suppress), the production
        #    admin convo (keyed by the real phone) has no UI surfacing it —
        #    the multi-volunteer test page polls ONLY +10000000000. Route
        #    the mirror to that test phone so the planner output shows up
        #    in the test panel. Without this override, the real-phone
        #    convo silently accumulates entries that no UI ever displays.
        from app.core.config import settings as _app_settings
        if _app_settings.sms_suppress:
            mirror_phone = "+10000000000"
        else:
            mirror_phone = admin_phone or "+10000000000"
        body_for_mirror = summary or (
            f"Recruitment planning failed for {event_label}. "
            "Open the dashboard to retry."
        )
        if summary:
            body_for_mirror = (
                body_for_mirror
                + "\n\nReply APPROVE to start, or open the dashboard to edit."
            )
        try:
            await executor._append_to_admin_conversation(
                db, tenant.id, mirror_phone, body_for_mirror
            )
        except Exception:
            logger.exception(
                "Failed to mirror plan summary to admin conversation "
                "for campaign %s", campaign.id,
            )

        # 3) If admin has a real phone, also send SMS (skips the mirror
        #    helper inside the SMS function — already mirrored above for
        #    the canonical admin conversation).
        if admin_phone:
            try:
                from app.services.sms import send_sms
                sms_body = body_for_mirror[:500]
                await send_sms(admin_phone, sms_body, tenant)
            except Exception:
                logger.exception(
                    "Failed to send planning SMS for campaign %s",
                    campaign.id,
                )
        else:
            logger.info(
                "Skipping planning SMS for campaign %s — admin has no "
                "phone configured (notification + admin convo mirror created)",
                campaign.id,
            )

        await db.commit()


def _goals_from_slot(
    slot: SpecificDateSlot, override_target: int | None = None
) -> list[dict]:
    """Derive recruitment goals from the slot's service_config.

    Each goal carries both ``min_required`` (must-fill) and ``max_allowed``
    (nice-to-have ceiling). If the admin overrides via ``override_target``,
    it sets the min; max stays at whatever the slot declared (or remains
    None so recruitment stops at min).
    """
    goals: list[dict] = []
    for entry in slot.service_config or []:
        sid = entry.get("appointment_type_id")
        if not sid:
            continue
        slot_min = int(entry.get("min_required", 1))
        slot_max = entry.get("max_allowed")
        try:
            slot_max_int: int | None = (
                int(slot_max) if slot_max is not None else None
            )
        except (TypeError, ValueError):
            slot_max_int = None
        min_required = (
            override_target if override_target is not None else slot_min
        )
        goals.append(
            {
                "appointment_type_id": str(sid),
                "min_required": int(min_required),
                "max_allowed": slot_max_int,
            }
        )
    return goals


async def _resolve_admin_user(ctx: ToolContext) -> AdminUser | None:
    """Find the AdminUser triggering this conversation.

    For admin chats, ``ctx.contact_id`` is set to ``admin_user.id`` by
    pipeline.py — fetch it from there. In test-tool flows, fall back to
    looking up by phone.
    """
    user = await ctx.db.get(AdminUser, ctx.contact_id) if ctx.contact_id else None
    if user:
        return user
    if ctx.contact_phone:
        result = await ctx.db.execute(
            select(AdminUser).where(
                AdminUser.tenant_id == ctx.tenant.id,
                AdminUser.phone == ctx.contact_phone,
                AdminUser.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
    return None


# ── Handlers ──


async def _list_upcoming_events_payload(ctx: ToolContext, limit: int = 10) -> list[dict]:
    """List active upcoming SpecificDateSlot rows for the tenant."""
    today = date.today()
    rows_q = await ctx.db.execute(
        select(SpecificDateSlot)
        .where(
            SpecificDateSlot.tenant_id == ctx.tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date >= today,
        )
        .order_by(SpecificDateSlot.date.asc())
        .limit(limit)
    )
    return [
        {
            "event_slot_id": str(s.id),
            "event_date": s.date.isoformat(),
            "label": s.label,
            "location": s.location,
        }
        for s in rows_q.scalars().all()
    ]


async def _resolve_event_slot(
    ctx: ToolContext,
    event_date_str: str | None,
    event_label: str | None,
) -> tuple[SpecificDateSlot | None, dict | None]:
    """Resolve a SpecificDateSlot from optional date and/or fuzzy label.

    Returns ``(slot, None)`` on a single unambiguous match. Returns
    ``(None, payload_dict)`` when the LLM needs to ask the admin to
    disambiguate or pick from a list — the dict is the JSON the tool
    should return.
    """
    today = date.today()

    # Parse date if provided
    event_date: date | None = None
    if event_date_str:
        try:
            event_date = date.fromisoformat(event_date_str)
        except ValueError:
            return None, {
                "error": "Invalid event_date format. Use YYYY-MM-DD."
            }

    # Build query — prefer active upcoming slots, narrow as filters are provided
    q = select(SpecificDateSlot).where(
        SpecificDateSlot.tenant_id == ctx.tenant.id,
        SpecificDateSlot.is_active.is_(True),
    )
    if event_date is not None:
        q = q.where(SpecificDateSlot.date == event_date)
    else:
        q = q.where(SpecificDateSlot.date >= today)
    if event_label:
        q = q.where(SpecificDateSlot.label.ilike(f"%{event_label}%"))
    q = q.order_by(SpecificDateSlot.date.asc()).limit(10)

    rows = list((await ctx.db.execute(q)).scalars().all())

    if len(rows) == 1:
        return rows[0], None

    # Zero matches: helpful fallback — show what IS upcoming so the admin
    # can pick or correct themselves.
    if not rows:
        upcoming = await _list_upcoming_events_payload(ctx)
        if event_date_str and not event_label:
            msg = f"No event on {event_date_str}."
        elif event_label and not event_date_str:
            msg = f"No upcoming event matches '{event_label}'."
        elif event_date_str and event_label:
            msg = (
                f"No upcoming event matches '{event_label}' on "
                f"{event_date_str}."
            )
        else:
            msg = (
                "Which event should I plan recruitment for? "
                "Here are the upcoming events."
            )
        return None, {
            "needs_clarification": True,
            "message": msg,
            "upcoming_events": upcoming,
        }

    # Multiple matches: ask the admin to pick.
    return None, {
        "needs_clarification": True,
        "message": (
            f"Multiple upcoming events match. Which one should I plan "
            f"recruitment for?"
        ),
        "matches": [
            {
                "event_slot_id": str(s.id),
                "event_date": s.date.isoformat(),
                "label": s.label,
                "location": s.location,
            }
            for s in rows
        ],
    }


async def handle_start_recruitment_campaign(
    ctx: ToolContext, tool_input: dict
) -> str:
    if not ctx.is_admin:
        return json.dumps({"error": "Recruitment is an admin-only feature."})

    slot, clarification = await _resolve_event_slot(
        ctx,
        event_date_str=tool_input.get("event_date"),
        event_label=tool_input.get("event_label"),
    )
    if clarification is not None:
        return json.dumps(clarification)
    assert slot is not None  # for type-narrowing

    admin_user = await _resolve_admin_user(ctx)
    if not admin_user:
        return json.dumps(
            {"error": "Could not resolve admin user for this conversation."}
        )

    # Reject duplicate active/pending campaigns for this slot
    existing_q = await ctx.db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == ctx.tenant.id,
            RecruitmentCampaign.event_slot_id == slot.id,
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.DRAFT,
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.ACTIVE,
                    CampaignStatus.PAUSED,
                ]
            ),
        )
    )
    if existing_q.scalar_one_or_none():
        return json.dumps(
            {
                "error": (
                    "A recruitment campaign is already in progress for this "
                    "event. Use recruitment_status to check it."
                )
            }
        )

    override = tool_input.get("target_per_service")
    goals = _goals_from_slot(
        slot, override_target=int(override) if override else None
    )
    if not goals:
        return json.dumps(
            {
                "error": (
                    "This event has no services configured. Use "
                    "manage_specific_date_slot to add services first."
                )
            }
        )

    # Optionally narrow to a single service
    service_name = tool_input.get("service_name")
    if service_name:
        from app.models.appointment_type import AppointmentType
        type_q = await ctx.db.execute(
            select(AppointmentType).where(
                AppointmentType.tenant_id == ctx.tenant.id,
                AppointmentType.name.ilike(service_name),
            )
        )
        appt = type_q.scalar_one_or_none()
        if not appt:
            return json.dumps(
                {"error": f"Service '{service_name}' not found."}
            )
        goals = [g for g in goals if g["appointment_type_id"] == str(appt.id)]
        if not goals:
            return json.dumps(
                {
                    "error": (
                        f"This event does not include the service "
                        f"'{service_name}'."
                    )
                }
            )

    campaign = RecruitmentCampaign(
        tenant_id=ctx.tenant.id,
        event_slot_id=slot.id,
        status=CampaignStatus.DRAFT,
        goals=goals,
        policy={},
        created_by_admin_id=admin_user.id,
    )
    ctx.db.add(campaign)
    await ctx.db.flush()
    await ctx.db.refresh(campaign)

    # CRITICAL: commit before scheduling the background task.
    # The planner opens its own AsyncSession and looks the campaign up by
    # id. Without an explicit commit here, the request's transaction is
    # still open when the task starts, the new session sees an empty DB,
    # and the planner silently aborts with "campaign not found" — leaving
    # the campaign stuck in DRAFT forever. FastAPI's get_db dependency
    # will commit again after the handler returns; SQLAlchemy treats a
    # second commit on an already-committed session as a no-op.
    try:
        await ctx.db.commit()
    except Exception:
        logger.exception(
            "Failed to commit draft campaign %s before scheduling planner",
            campaign.id,
        )
        return json.dumps(
            {"error": "Could not save campaign. Please try again."}
        )

    # Schedule the planner without blocking the SMS response.
    # Strong reference via _BACKGROUND_TASKS — asyncio.create_task alone is
    # GC-vulnerable and the task can be collected before it runs.
    _schedule_background(
        _kick_off_planner_task(
            campaign.id,
            admin_user.phone,
            admin_user_id=admin_user.id,
        )
    )
    logger.info(
        "Scheduled planner for campaign %s (admin_phone=%s, in_flight=%d)",
        campaign.id, admin_user.phone, len(_BACKGROUND_TASKS),
    )

    will_sms = bool(admin_user.phone)
    # Mask the phone in user-facing text but keep enough to recognize it.
    masked_phone = ""
    if admin_user.phone:
        p = admin_user.phone
        masked_phone = p[:3] + "***" + p[-4:] if len(p) >= 7 else p
    msg = (
        (
            f"Planning started for {slot.label or 'event'} on "
            f"{slot.date.isoformat()}. I'll text the proposed plan to "
            f"{masked_phone} in about a minute and also post it to "
            "your dashboard's Notifications panel."
        )
        if will_sms
        else (
            f"Planning started for {slot.label or 'event'} on "
            f"{slot.date.isoformat()}. Your account ({admin_user.email}) "
            "has no phone configured, so the proposed plan will appear "
            "in your dashboard's Notifications panel in a minute (no SMS)."
        )
    )

    # Log what we actually resolved so we can diagnose if the LLM
    # generates incorrect wording downstream.
    logger.info(
        "start_recruitment_campaign tool resolved admin %s (id=%s) "
        "phone=%r will_sms=%s",
        admin_user.email, admin_user.id, admin_user.phone, will_sms,
    )

    return json.dumps(
        {
            "ok": True,
            "campaign_id": str(campaign.id),
            "event_date": slot.date.isoformat(),
            "event_label": slot.label,
            "admin_email": admin_user.email,
            "admin_phone_configured": will_sms,
            "delivery_channel": "sms+dashboard" if will_sms else "dashboard-only",
            "message": msg,
        }
    )


async def handle_approve_recruitment_campaign(
    ctx: ToolContext, tool_input: dict
) -> str:
    from app.agents.recruiter import executor

    if not ctx.is_admin:
        return json.dumps({"error": "Recruitment is an admin-only feature."})

    admin_user = await _resolve_admin_user(ctx)
    if not admin_user:
        return json.dumps(
            {"error": "Could not resolve admin user for this conversation."}
        )

    campaign_id_str = tool_input.get("campaign_id")
    campaign: RecruitmentCampaign | None = None
    if campaign_id_str:
        try:
            cid = uuid.UUID(campaign_id_str)
        except (ValueError, TypeError):
            return json.dumps({"error": "Invalid campaign_id."})
        candidate = await ctx.db.get(RecruitmentCampaign, cid)
        if not candidate or candidate.tenant_id != ctx.tenant.id:
            return json.dumps({"error": "Campaign not found."})
        campaign = candidate
    else:
        # Most recent awaiting_approval campaign for this tenant
        q = await ctx.db.execute(
            select(RecruitmentCampaign)
            .where(
                RecruitmentCampaign.tenant_id == ctx.tenant.id,
                RecruitmentCampaign.status == CampaignStatus.AWAITING_APPROVAL,
            )
            .order_by(desc(RecruitmentCampaign.updated_at))
            .limit(1)
        )
        campaign = q.scalar_one_or_none()
        if not campaign:
            return json.dumps(
                {
                    "error": (
                        "No campaign is currently awaiting approval. Start "
                        "one with start_recruitment_campaign."
                    )
                }
            )

    if campaign.status != CampaignStatus.AWAITING_APPROVAL:
        return json.dumps(
            {
                "error": (
                    f"Campaign is in status {campaign.status.value}; only "
                    "awaiting_approval campaigns can be approved."
                )
            }
        )

    slot = await ctx.db.get(SpecificDateSlot, campaign.event_slot_id)
    if not slot:
        return json.dumps({"error": "Event slot has been deleted."})

    campaign.status = CampaignStatus.ACTIVE
    campaign.approved_by_admin_id = admin_user.id
    campaign.approved_at = datetime.now(timezone.utc)
    await ctx.db.flush()
    waves = await executor.materialize_waves_on_approval(
        ctx.db, campaign, slot
    )
    await ctx.db.flush()

    # Commit before scheduling the immediate tick — same race-condition
    # guard we use for start_recruitment_campaign. Without it, the tick
    # task opens a fresh session and may not see the approval flip yet.
    try:
        await ctx.db.commit()
    except Exception:
        logger.exception(
            "Failed to commit approval for campaign %s", campaign.id
        )
        return json.dumps({"error": "Could not save approval. Try again."})

    # Fire any due waves immediately (wave 1 is always due thanks to the
    # snap-to-now logic in materialize_waves_on_approval). Without this
    # the admin would wait up to 15 min for the next scheduled tick.
    _schedule_background(executor.run_tick_for_campaign(campaign.id))

    return json.dumps(
        {
            "ok": True,
            "campaign_id": str(campaign.id),
            "status": campaign.status.value,
            "waves_scheduled": len(waves),
            "first_wave_at": min(
                (w.scheduled_at.isoformat() for w in waves), default=None
            ),
            "message": (
                "Campaign approved and the first wave is going out now."
            ),
        }
    )


APPROVAL_PHRASES = {
    "approve",
    "approved",
    "yes",
    "y",
    "go",
    "go ahead",
    "do it",
    "start",
    "launch",
    "start it",
    "proceed",
    "sounds good",
    "looks good",
    "lgtm",
    "ok",
    "okay",
    "sure",
    "yep",
    "✓",
    "✅",
    "approve it",
    "approve campaign",
    "approve the campaign",
    "approve the plan",
    "approve plan",
    "yes approve",
    "yes please",
}


async def maybe_handle_approval_directly(
    db,
    tenant: Tenant,
    message: str,
    admin_user: AdminUser | None,
) -> str | None:
    """Server-side router for unambiguous approval phrases.

    Bypasses the LLM when the admin's full message is a clear approval
    word/phrase AND there's a campaign awaiting approval for the tenant.
    Returns a confirmation string (becomes the assistant reply) when it
    handles the message, ``None`` to fall through to the LLM.

    Necessary because the LLM kept hallucinating "Approved!" without
    actually invoking ``approve_recruitment_campaign`` despite explicit
    routing rules. Server-side routing makes approval reliable.
    """
    from app.agents.recruiter import executor

    if not message or not admin_user:
        return None
    text = message.strip().lower()
    # Strip simple trailing punctuation
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()
    if text not in APPROVAL_PHRASES:
        return None

    # Find most recent awaiting_approval campaign
    q = await db.execute(
        select(RecruitmentCampaign)
        .where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status == CampaignStatus.AWAITING_APPROVAL,
        )
        .order_by(desc(RecruitmentCampaign.updated_at))
        .limit(1)
    )
    campaign = q.scalar_one_or_none()
    if not campaign:
        # No pending campaign. We INTERCEPT instead of falling through —
        # the LLM otherwise happily hallucinates "✅ Approved!" from
        # nothing (cascading from any earlier turn where it pretended a
        # plan existed). Honest "nothing to approve" stops the cascade.
        # See design_decisions.md #7/#20 lineage.
        logger.info(
            "Approval intent received but no AWAITING_APPROVAL campaign "
            "exists for tenant %s — intercepting with no-op reply",
            tenant.id,
        )
        return (
            "There's no recruitment plan waiting for your approval. "
            "Say 'plan recruitment for <event>' to start a new one, or "
            "'list active campaigns' to see what's currently running."
        )

    slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
    if not slot:
        return None

    # Approve + materialize waves + kick immediate tick.
    campaign.status = CampaignStatus.ACTIVE
    campaign.approved_by_admin_id = admin_user.id
    campaign.approved_at = datetime.now(timezone.utc)
    await db.flush()
    waves = await executor.materialize_waves_on_approval(db, campaign, slot)
    await db.flush()
    try:
        await db.commit()
    except Exception:
        logger.exception(
            "Auto-approval commit failed for campaign %s", campaign.id
        )
        return None

    _schedule_background(executor.run_tick_for_campaign(campaign.id))
    logger.info(
        "Auto-approved campaign %s via server-side intent router "
        "(message=%r, waves=%d)",
        campaign.id, message, len(waves),
    )
    label = slot.label or "the event"
    return (
        f"Campaign approved for {label} on {slot.date.isoformat()}. "
        "Outreach is starting now — first wave going out within seconds. "
        "I'll text you a daily progress update."
    )


# ── Server-side intent router: start a recruitment campaign ──
# Same playbook as maybe_handle_approval_directly above (decision #7):
# the LLM was hallucinating "Planning started" confirmations without
# actually calling start_recruitment_campaign — see design_decisions.md
# #20. This router catches unambiguous trigger phrases ("plan for X",
# "recruit volunteers for X", etc.), extracts the event reference, and
# calls the existing handle_start_recruitment_campaign directly. Falls
# through (returns None) for anything ambiguous, letting the LLM handle
# the conversation normally.

import re as _re

# Regex patterns — each captures group 1 = the event-reference subject.
# Anchored at start of message (after lowercasing + strip) to avoid
# catching phrases embedded in longer questions ("can you tell me how
# we plan for X" → not a planning command, the LLM should reply with
# explanation).
_START_CAMPAIGN_PATTERNS = [
    # "i want to plan / can we plan / could you plan" — softer phrasings.
    # Note `start\s+plan(?:ning)?` accepts both "start plan" and "start planning".
    _re.compile(r"^(?:i\s+(?:want|need|would\s+like)\s+to\s+|can\s+(?:you|we)\s+|could\s+you\s+)(?:please\s+)?(?:plan|start\s+plan(?:ning)?|recruit|launch\s+(?:a\s+)?campaign|start\s+(?:a\s+)?campaign|fill|staff)\s+(?:a\s+campaign\s+)?(?:volunteers?\s+)?(?:for\s+|the\s+|a\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?start\s+plan(?:ning)?\s+(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?plan(?:ning)?\s+(?:a\s+campaign\s+)?(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?recruit\s+(?:volunteers?\s+)?(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?(?:launch|start)\s+(?:a\s+)?campaign\s+(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?campaign\s+(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?fill\s+(?:the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?staff\s+(?:the\s+)?(.+)$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?outreach\s+(?:for\s+|the\s+)?(.+)$"),
    _re.compile(r"^(?:i\s+)?need\s+volunteers?\s+(?:for\s+|the\s+)?(.+)$"),
]

# BARE planning intent — no event reference. Match these explicitly so
# the LLM never gets a chance to hallucinate "planning started" for an
# unspecified event. When matched, the router asks which event (or
# auto-picks if exactly one upcoming exists). See design_decisions.md #20.
# Accepts both "plan" and "planning" everywhere via plan(?:ning)?.
_BARE_START_CAMPAIGN_PATTERNS = [
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?start\s+plan(?:ning)?\.?$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?plan(?:ning)?\.?$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?(?:launch|start)\s+(?:a\s+)?campaign\.?$"),
    _re.compile(r"^(?:let'?s\s+)?(?:please\s+)?recruit(?:\s+volunteers?)?\.?$"),
    _re.compile(r"^(?:i\s+(?:want|need|would\s+like)\s+to\s+|can\s+(?:you|we)\s+|could\s+you\s+)(?:please\s+)?(?:plan|start\s+plan(?:ning)?|recruit|launch\s+(?:a\s+)?campaign|start\s+(?:a\s+)?campaign)\.?$"),
]

# Inline date extractor — handles the common natural-language forms
# admins actually type. Returns (date_iso_string, leftover_label) or
# (None, original_string) if no date found.
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
# "june 15", "jun 15th", "june 15, 2026", "15 june", "15 jun 2026"
_MONTH_NAME_DATE_RE = _re.compile(
    r"\b(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?"
    r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|"
    r"aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
    r"(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?"
    r"(?:[,\s]+(\d{4}))?\b",
    _re.IGNORECASE,
)
# "6/15", "06/15/2026", "2026-06-15"
_NUMERIC_DATE_RE = _re.compile(
    r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b|"
    r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"
)


def _extract_date_from_text(text: str) -> tuple[str | None, str]:
    """Pull the first recognizable date out of `text`. Returns (iso_date
    or None, text with the matched date span removed)."""
    from datetime import date as _date

    today = _date.today()

    # Try ISO / numeric first (less likely to false-match)
    m = _NUMERIC_DATE_RE.search(text)
    if m:
        if m.group(1):  # ISO YYYY-MM-DD
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            month, day = int(m.group(4)), int(m.group(5))
            year_raw = m.group(6)
            if year_raw:
                year = int(year_raw) if len(year_raw) == 4 else 2000 + int(year_raw)
            else:
                # No year → pick next upcoming occurrence
                year = today.year
                try:
                    candidate = _date(year, month, day)
                except ValueError:
                    return None, text
                if candidate < today:
                    year += 1
        try:
            iso = _date(year, month, day).isoformat()
            leftover = (text[: m.start()] + text[m.end():]).strip()
            return iso, leftover
        except ValueError:
            pass  # invalid date — fall through

    # Month-name format
    m = _MONTH_NAME_DATE_RE.search(text)
    if m:
        # Day might be in group 1 (before month) or group 3 (after month)
        day_str = m.group(1) or m.group(3)
        month_str = m.group(2).lower()
        year_str = m.group(4)
        if day_str and month_str in _MONTHS:
            day = int(day_str)
            month = _MONTHS[month_str]
            year = int(year_str) if year_str else today.year
            try:
                candidate = _date(year, month, day)
            except ValueError:
                return None, text
            if not year_str and candidate < today:
                # No year provided + date is past → assume next year
                candidate = _date(year + 1, month, day)
            leftover = (text[: m.start()] + text[m.end():]).strip()
            return candidate.isoformat(), leftover

    return None, text


_LABEL_NOISE_WORDS = {
    "recruitment", "recruit", "outreach", "event", "events", "campaign",
    "the", "a", "an", "for", "on", "at", "to", "in", "of", "by",
    "please", "lets", "let's", "i", "we", "want", "need",
}


def _clean_label(text: str) -> str:
    """Strip filler words from a label string so noisy phrasings like
    'recruitment event for food drive on' resolve cleanly to a slot
    labeled 'Food Drive'.

    Removes _LABEL_NOISE_WORDS from anywhere in the text, not just the
    edges. Returns the joined remainder. If nothing's left, returns ''
    (router will fall back to date-only resolution).
    """
    text = text.strip().strip("?.!,;").strip()
    if not text:
        return ""
    tokens = text.split()
    cleaned = [t for t in tokens if t.lower() not in _LABEL_NOISE_WORDS]
    return " ".join(cleaned).strip()


async def maybe_handle_start_campaign_directly(
    ctx: ToolContext,
    message: str,
) -> str | None:
    """Server-side router for unambiguous campaign-start phrases.

    Bypasses the LLM when the admin's message clearly says "plan for X" /
    "recruit for X" / "fill X" / etc. Extracts the event reference and
    calls the existing handle_start_recruitment_campaign with whatever
    parameters are recoverable from the message text. Returns the
    handler's user-facing message string on success, or None to fall
    through to the LLM.

    Necessary because the LLM kept hallucinating "Planning started"
    confirmations without invoking start_recruitment_campaign — same
    pattern as decision #7's approve/status routers. See design_decisions.md
    #20.
    """
    if not ctx.is_admin or not message:
        return None
    text = message.strip().lower()
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()
    if not text:
        return None

    # Check BARE patterns first ("start planning" with no event ref).
    # If matched, we never fall through to the LLM — bare planning
    # intent without an event reference is exactly where the LLM
    # cascades into hallucination. Intercept and clarify.
    if any(p.match(text) for p in _BARE_START_CAMPAIGN_PATTERNS):
        logger.info(
            "Bare start-planning intent detected (message=%r) — "
            "looking up upcoming events for disambiguation",
            message,
        )
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        horizon = today + _td(days=60)
        # Look at upcoming one-off events. If exactly one, target it.
        # If 0, tell admin to create one first. If multiple, ask which.
        slots_q = await ctx.db.execute(
            select(SpecificDateSlot)
            .where(
                SpecificDateSlot.tenant_id == ctx.tenant.id,
                SpecificDateSlot.is_active.is_(True),
                SpecificDateSlot.date >= today,
                SpecificDateSlot.date <= horizon,
            )
            .order_by(SpecificDateSlot.date.asc())
            .limit(8)
        )
        slots = list(slots_q.scalars().all())
        if not slots:
            return (
                "There are no upcoming events to plan recruitment for. "
                "Create an event first (tell me 'create event for <date> "
                "<label>'), then ask me to plan recruitment."
            )
        if len(slots) == 1:
            slot = slots[0]
            logger.info(
                "Single upcoming event found — auto-targeting %s (%s)",
                slot.label, slot.date,
            )
            raw = await handle_start_recruitment_campaign(
                ctx,
                {"event_date": slot.date.isoformat(), "event_label": slot.label},
            )
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    if parsed.get("ok") and "message" in parsed:
                        return parsed["message"]
                    if "error" in parsed:
                        return f"Couldn't start planning: {parsed['error']}"
                    if parsed.get("needs_clarification"):
                        return (
                            f"I'd plan for {slot.label} on {slot.date.isoformat()}, "
                            "but the tool needs more info. Try 'plan recruitment "
                            f"for {slot.label} on {slot.date.isoformat()}'."
                        )
            except json.JSONDecodeError:
                pass
            return raw
        # Multiple — ask which
        lines = "\n".join(
            f"  • {s.label or 'event'} on {s.date.isoformat()}"
            for s in slots[:5]
        )
        return (
            "Which event do you want to plan recruitment for?\n"
            f"{lines}\n"
            "Reply with 'plan recruitment for <name>' or 'plan recruitment "
            "for <YYYY-MM-DD>'."
        )

    subject: str | None = None
    for pattern in _START_CAMPAIGN_PATTERNS:
        m = pattern.match(text)
        if m:
            subject = m.group(1).strip()
            break

    if subject is None:
        return None

    # Extract a date from the subject if present; remainder is the label
    iso_date, leftover = _extract_date_from_text(subject)
    label = _clean_label(leftover) if leftover else ""
    # Treat very short cleaned labels as "no usable label" — single
    # words like "the" or "of" that survived can poison the ILIKE match.
    if len(label) < 3:
        label = ""

    # If we extracted nothing useful (no date AND no label), fall through.
    # The LLM might handle "plan for it" or similar context-dependent input
    # better than we can.
    if not iso_date and not label:
        return None

    # Two-pass dispatch: first try with whatever args we've got. If that
    # returns needs_clarification AND we have a date, retry with the
    # date alone — that's almost always uniquely resolvable.
    async def _dispatch(tool_input: dict) -> str:
        logger.info(
            "Auto-routing start_recruitment_campaign via intent router "
            "(message=%r, extracted=%s)",
            message, tool_input,
        )
        return await handle_start_recruitment_campaign(ctx, tool_input)

    first_input: dict = {}
    if iso_date:
        first_input["event_date"] = iso_date
    if label:
        first_input["event_label"] = label

    raw_response = await _dispatch(first_input)

    def _parse(raw: str) -> dict | None:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    parsed = _parse(raw_response)
    if parsed is None:
        return raw_response

    # Date-only fallback when label is the culprit
    if (
        parsed.get("needs_clarification")
        and iso_date
        and label
    ):
        logger.info(
            "First-pass extraction returned needs_clarification; "
            "retrying with date-only (label %r was likely too noisy)",
            label,
        )
        raw_response = await _dispatch({"event_date": iso_date})
        parsed = _parse(raw_response) or parsed

    if parsed.get("ok") and "message" in parsed:
        return parsed["message"]
    if "error" in parsed:
        return f"Couldn't start planning: {parsed['error']}"
    if parsed.get("needs_clarification"):
        # Build a useful clarification reply from the handler's data
        # rather than fall through (which lets the LLM hallucinate).
        # Note: payloads use `event_date`; older callers / tests may
        # use `date`. Read both.
        matches = parsed.get("matches") or []
        upcoming = parsed.get("upcoming_events") or []
        if matches and len(matches) > 1:
            lines = "\n".join(
                f"  • {m.get('label', 'event')} on "
                f"{m.get('event_date') or m.get('date') or '?'}"
                for m in matches[:5]
            )
            return (
                "Which event did you mean? I found multiple matches:\n"
                f"{lines}\n"
                "Reply with the date (YYYY-MM-DD) or a more specific name."
            )
        if upcoming:
            lines = "\n".join(
                f"  • {u.get('label', 'event')} on "
                f"{u.get('event_date') or u.get('date') or '?'}"
                for u in upcoming[:5]
            )
            return (
                "I couldn't find a match. Here are the upcoming events:\n"
                f"{lines}\n"
                "Reply with the date or label of the one you meant."
            )
        return (
            "I couldn't identify which event you meant. Could you say "
            "the event date (YYYY-MM-DD) or label?"
        )
    return None


# ── Server-side intent router: delete a recruitment campaign ──
# Same playbook as maybe_handle_start_campaign_directly above
# (decision #21, sibling to #20). DELETE is destructive — we ONLY
# match the explicit verb "delete" (not "cancel" or "remove" which
# admins might mean for events, not campaigns).

# Each pattern captures group 1 = the campaign reference subject.
# All require the explicit "delete" verb at the start.
_DELETE_CAMPAIGN_PATTERNS = [
    # Bare-pronoun forms: "delete it", "delete this", "delete that",
    # "delete this muster", "delete that one", "delete the muster".
    # Subject is empty/pronoun → router falls back to unique-active
    # lookup. "campaign" is kept for backward compatibility but is
    # ambiguous once Fundraising / Recruiting Campaigns ship — admins
    # should prefer "muster" in new phrasing.
    _re.compile(r"^(?:please\s+)?delete\s+(?:it|this|that|the\s+one|that\s+one)$"),
    _re.compile(r"^(?:please\s+)?delete\s+(?:this|that|the)\s+(?:recruitment\s+)?(?:muster|campaign)\.?$"),
    _re.compile(r"^(?:please\s+)?delete\s+(?:this|that|the)\s+(?:recruitment|planning|plan)\.?$"),
    # "delete (the) X muster", "delete (the) muster for X"
    _re.compile(r"^(?:please\s+)?delete\s+(?:the\s+)?(?:recruitment\s+)?(?:muster|campaign)\s+(?:for\s+|on\s+|to\s+)?(.+)$"),
    _re.compile(r"^(?:please\s+)?delete\s+(?:the\s+)?(.+?)\s+(?:recruitment\s+)?(?:muster|campaign)\b.*$"),
    # "delete planning for X" / "delete the plan for X"
    _re.compile(r"^(?:please\s+)?delete\s+(?:the\s+)?planning\s+(?:for\s+)?(.+)$"),
    _re.compile(r"^(?:please\s+)?delete\s+(?:the\s+)?plan\s+(?:for\s+)?(.+)$"),
    # "delete the recruitment for X"
    _re.compile(r"^(?:please\s+)?delete\s+(?:the\s+)?recruitment\s+(?:for\s+)?(.+)$"),
]

# Subjects that mean "the unique active muster in this tenant" — used
# by the pronoun fallback. Lowercased, no punctuation.
_DELETE_PRONOUN_SUBJECTS = {
    "", "this", "that", "it", "the one", "that one",
    "this muster", "that muster", "the muster",
    "this campaign", "that campaign", "the campaign",
    "this recruitment", "that recruitment", "the recruitment",
    "this planning", "that planning", "the planning",
    "this plan", "that plan", "the plan",
}


async def maybe_handle_delete_campaign_directly(
    ctx: ToolContext,
    message: str,
) -> str | None:
    """Server-side router for unambiguous campaign-delete phrases.

    Bypasses the LLM when the admin's message starts with "delete (the)
    X campaign" / "delete planning for X" / etc. Extracts the event
    reference + dispatches to handle_delete_recruitment_campaign.
    Returns None to fall through to the LLM when:
      - no trigger phrase matches (admin meant something else)
      - extraction produces no usable date AND no usable label
      - handler returns needs_clarification with multiple matches —
        list them in a clarification reply (not None) so the LLM
        doesn't get a chance to hallucinate "✓ deleted"

    Trusts the explicit "delete" verb as consent. Confirmation isn't
    a separate turn — the explicit verb IS the confirmation. If admins
    accidentally hit this, we can add a two-turn dance later; for now,
    match the file-deletion pattern (admin types `rm X` = X is gone).
    """
    if not ctx.is_admin or not message:
        return None
    text = message.strip().lower()
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()
    if not text:
        return None

    subject: str | None = None
    for pattern in _DELETE_CAMPAIGN_PATTERNS:
        m = pattern.match(text)
        if m:
            # Bare-pronoun patterns have no capture group (group() with
            # index 1 raises). Treat those as empty subject so the
            # pronoun fallback below kicks in.
            try:
                subject = m.group(1).strip()
            except IndexError:
                subject = ""
            break

    if subject is None:
        return None

    # Pronoun fallback: when the admin says "delete it" / "delete this
    # campaign" / etc. with no specific event reference, look up the
    # unique non-terminal campaign for this tenant. If exactly one
    # exists, target it directly. If zero or multiple, ask.
    if subject in _DELETE_PRONOUN_SUBJECTS:
        active_q = await ctx.db.execute(
            select(RecruitmentCampaign)
            .where(
                RecruitmentCampaign.tenant_id == ctx.tenant.id,
                RecruitmentCampaign.status.in_(
                    [
                        CampaignStatus.DRAFT,
                        CampaignStatus.AWAITING_APPROVAL,
                        CampaignStatus.ACTIVE,
                        CampaignStatus.PAUSED,
                    ]
                ),
            )
            .order_by(desc(RecruitmentCampaign.updated_at))
        )
        active = list(active_q.scalars().all())
        if not active:
            return (
                "There are no active campaigns to delete. "
                "Use 'list active campaigns' to see what exists."
            )
        if len(active) > 1:
            lines = []
            for c in active[:5]:
                slot = await ctx.db.get(SpecificDateSlot, c.event_slot_id)
                slot_label = (
                    slot.label if slot and slot.label else "event"
                )
                slot_date = (
                    slot.date.isoformat() if slot and slot.date else "?"
                )
                lines.append(
                    f"  • {slot_label} on {slot_date} ({c.status.value})"
                )
            return (
                "Multiple active campaigns. Which one?\n"
                + "\n".join(lines)
                + "\nReply with the date (YYYY-MM-DD) or the event name."
            )
        # Exactly one — dispatch with the explicit campaign_id
        target = active[0]
        logger.info(
            "Auto-routing delete_recruitment_campaign via pronoun "
            "fallback (message=%r, campaign=%s)",
            message, target.id,
        )
        raw_response = await handle_delete_recruitment_campaign(
            ctx, {"campaign_id": str(target.id)}
        )
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return raw_response
        if isinstance(parsed, dict):
            if parsed.get("ok") and "message" in parsed:
                return parsed["message"]
            if "error" in parsed:
                return f"Couldn't delete: {parsed['error']}"
        return None

    # Extract a date + label using the same helpers as the start router.
    iso_date, leftover = _extract_date_from_text(subject)
    label = _clean_label(leftover) if leftover else ""
    if len(label) < 3:
        label = ""

    if not iso_date and not label:
        return None

    logger.info(
        "Auto-routing delete_recruitment_campaign via intent router "
        "(message=%r, date=%s, label=%r)",
        message, iso_date, label,
    )

    async def _dispatch(tool_input: dict) -> str:
        return await handle_delete_recruitment_campaign(ctx, tool_input)

    first_input: dict = {}
    if iso_date:
        first_input["event_date"] = iso_date
    if label:
        first_input["event_label"] = label

    raw_response = await _dispatch(first_input)

    def _parse(raw: str) -> dict | None:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    parsed = _parse(raw_response)
    if parsed is None:
        return raw_response

    # Date-only retry when label is noisy
    if (
        parsed.get("needs_clarification")
        and iso_date
        and label
    ):
        logger.info(
            "Delete first-pass returned needs_clarification; retrying "
            "with date-only (label %r was likely too noisy)",
            label,
        )
        raw_response = await _dispatch({"event_date": iso_date})
        parsed = _parse(raw_response) or parsed

    if parsed.get("ok") and "message" in parsed:
        return parsed["message"]
    if "error" in parsed:
        return f"Couldn't delete: {parsed['error']}"
    if parsed.get("needs_clarification"):
        # Two flavors of clarification:
        # 1) Multiple campaigns for one slot — show their UUIDs + status
        # 2) Multiple slot matches — show date + label
        # Note: the upcoming/matches payloads from _resolve_event_slot
        # and _list_upcoming_events_payload use `event_date`, not `date`.
        matches = parsed.get("matches") or []
        upcoming = parsed.get("upcoming_events") or []
        if matches and isinstance(matches[0], dict) and "campaign_id" in matches[0]:
            lines = "\n".join(
                f"  • {m['campaign_id'][:8]} ({m.get('status', '?')}, created {(m.get('created_at') or '?')[:10]})"
                for m in matches[:5]
            )
            return (
                "Multiple campaigns match. Which one?\n"
                f"{lines}\n"
                "Reply with the first 8 chars of the campaign id (or the full id)."
            )
        if matches:
            lines = "\n".join(
                f"  • {m.get('label', 'event')} on "
                f"{m.get('event_date') or m.get('date') or '?'}"
                for m in matches[:5]
            )
            return (
                "Which event's campaign did you mean? I found multiple matches:\n"
                f"{lines}\n"
                "Reply with the date (YYYY-MM-DD) or a more specific name."
            )
        if upcoming:
            lines = "\n".join(
                f"  • {u.get('label', 'event')} on "
                f"{u.get('event_date') or u.get('date') or '?'}"
                for u in upcoming[:5]
            )
            return (
                "I couldn't find a campaign for that event. Upcoming events:\n"
                f"{lines}\n"
                "Reply with the date or label of the event whose campaign you want deleted."
            )
        return (
            "I couldn't identify which campaign you meant. Could you say "
            "the event date (YYYY-MM-DD) or label?"
        )
    return None


# ── Server-side intent router: list upcoming events ──
# Backstop for the LLM ignoring the "call manage_specific_date_slot
# action='list' for event-list queries" rule in the admin preamble.
# The preamble already shows event labels + dates so the LLM keeps
# answering from memory instead of fetching volunteer counts. This
# router fires the tool deterministically when the admin asks for
# upcoming events.

_LIST_EVENTS_PATTERNS = [
    _re.compile(r"^(?:please\s+)?(?:list|show|what(?:'s|\s+are)?|tell\s+me\s+about|see)\s+(?:the\s+)?(?:my\s+|all\s+)?upcoming\s+events\.?$"),
    _re.compile(r"^(?:please\s+)?(?:list|show)\s+(?:the\s+)?(?:my\s+|all\s+)?events\.?$"),
    _re.compile(r"^(?:what(?:'s|\s+is)|what\s+are)\s+coming\s+up\??\.?$"),
    _re.compile(r"^(?:what(?:'s|\s+is)?)\s+(?:on\s+)?(?:my\s+|the\s+)?(?:upcoming\s+)?calendar\??\.?$"),
    _re.compile(r"^(?:what(?:'s|\s+is)?)\s+(?:on\s+)?(?:the\s+)?(?:upcoming\s+)?schedule\??\.?$"),
    _re.compile(r"^upcoming\s+events\??\.?$"),
    _re.compile(r"^events\s+coming\s+up\??\.?$"),
]


async def maybe_handle_list_events_directly(
    ctx: ToolContext,
    message: str,
) -> str | None:
    """Server-side router for unambiguous 'list upcoming events' phrases.

    Bypasses the LLM and calls handle_manage_specific_date_slot
    action='list' directly, then renders the response into a friendly
    multi-line text reply. Returns None (fall through to LLM) when no
    trigger matches.

    Necessary because the admin state preamble (decision #8) lists
    event labels + dates inline, so the LLM kept answering 'list
    events' from memory and skipping the full-detail tool — losing
    recurring events and all volunteer-count data.
    """
    if not ctx.is_admin or not message:
        return None
    text = message.strip().lower()
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()
    if not text:
        return None

    matched = any(p.match(text) for p in _LIST_EVENTS_PATTERNS)
    if not matched:
        return None

    logger.info(
        "Auto-routing manage_specific_date_slot action=list via "
        "intent router (message=%r)",
        message,
    )

    # Defer the import to avoid the top-level cycle that already exists
    # between chat_tools and tool_handlers.
    from app.modules.tool_handlers import handle_manage_specific_date_slot

    raw = await handle_manage_specific_date_slot(ctx, {"action": "list"})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(parsed, dict) and parsed.get("message"):
        # The "no events configured" message
        return parsed["message"]

    events = (parsed.get("events") if isinstance(parsed, dict) else None) or []
    if not events:
        return "No upcoming events in the next 4 weeks."

    summary = parsed.get("summary", {})
    horizon = parsed.get("horizon_days", 28)

    # Render — concise, scannable, SMS-friendly. Group implicitly by
    # date (already sorted by the handler).
    lines = [
        f"Upcoming events (next {horizon} days, "
        f"{summary.get('one_off_count', 0)} one-off + "
        f"{summary.get('recurring_count', 0)} recurring):",
        "",
    ]
    for ev in events:
        date_str = ev.get("date", "?")
        label = ev.get("label") or ("recurring program" if ev.get("kind") == "recurring" else "event")
        start = ev.get("start", "")
        end = ev.get("end", "")
        time_str = f" {start}-{end}" if start and end else (f" {start}" if start else "")
        loc = ev.get("location") or ""
        recur = ev.get("recurrence") or ""
        recur_tag = f" [{recur}]" if recur else ""
        needed = ev.get("total_needed", 0)
        signed = ev.get("total_signed_up", 0)
        more = ev.get("more_required", 0)

        line = f"• {label} — {date_str}{time_str}{recur_tag}"
        if loc:
            line += f" @ {loc}"
        lines.append(line)
        if needed > 0:
            lines.append(
                f"  {signed}/{needed} signed up — {more} more required"
            )

    lines.append("")
    lines.append(
        "Want details on any of these? Tell me the event name or date "
        "and I'll pull the roster or campaign status."
    )
    return "\n".join(lines)


# Substring patterns that indicate an unambiguous "what campaigns are
# running?" question. Each tuple = (must_have_one_of, must_have_one_of)
# — both groups must hit. Kept conservative so we don't intercept genuine
# planning requests.
_STATUS_TRIGGER_PAIRS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (
        ("campaign", "campaigns", "recruitment"),
        (
            "active",
            "running",
            "status",
            "in progress",
            "happening",
            "ongoing",
            "current",
            "list",
            "show",
            "any",
            "what",
            "which",
            "how many",
        ),
    ),
    # Time-window phrasings — "this week's status", "today's status",
    # "what's happening tomorrow" — without requiring the word "campaign".
    # Admins routinely ask in time-window form; the previous trigger set
    # silently fell through to the LLM, which would happily render any
    # active campaign as the answer.
    (
        (
            "this week",
            "next week",
            "today",
            "tomorrow",
            "this month",
            "next month",
        ),
        ("status", "happening", "going on", "scheduled", "events"),
    ),
]


def _looks_like_status_query(message: str) -> bool:
    if not message:
        return False
    text = message.strip().lower()
    # Strip simple trailing punctuation but keep internal characters
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    if not text:
        return False
    # Reject anything that includes the strong planning verbs — those
    # should still route to start_recruitment_campaign.
    PLANNING_VERBS = (
        "plan ",
        "fill ",
        "staff ",
        "recruit ",
        "outreach ",
        "volunteers for ",
        "get people for ",
        "start a campaign",
        "create campaign",
        "new campaign",
    )
    if any(v in text for v in PLANNING_VERBS):
        return False
    for must_a, must_b in _STATUS_TRIGGER_PAIRS:
        if any(a in text for a in must_a) and any(b in text for b in must_b):
            return True
    return False


async def maybe_handle_status_directly(
    db,
    tenant: Tenant,
    message: str,
    admin_id: uuid.UUID | None = None,
) -> str | None:
    """Server-side router for unambiguous status questions.

    Two paths:

      1. Initial query (or one carrying an event filter):
         - "status of awareness seminar" / "status of campaigns on Jul 4" →
           filter narrows to one campaign → render the full block (totals,
           per-service breakdown, wave history).
         - "status of campaigns" with no filter and N>1 results → render a
           SHORT numbered list ("1. Awareness Seminar — 2026-06-14 [active]")
           and persist the list keyed to ``admin_id`` so the next SMS can
           pick one. SMS gets too long otherwise — a list of N full blocks
           would blow past Twilio segment limits the moment N > 2.

      2. Follow-up selection ("1" / "awareness seminar" / "Jul 4"):
         - If ``admin_id`` has a saved pending list, the message is matched
           against it (ordinal → date → label substring) and we render that
           one campaign's full block.

    Without ``admin_id`` we can't persist or recall — the function falls
    back to the legacy "render every campaign" behavior (still better than
    dumping nothing). The pipeline.py + intent_dispatch admin paths
    always pass admin_id; the test_conversation tool passes None.
    """
    from app.models.availability import SpecificDateSlot
    from app.models.appointment_type import AppointmentType

    # ── Path 2: follow-up selection against a saved list ──────────
    if admin_id is not None:
        pending = await _load_pending_status_list(db, tenant.id, admin_id)
        if pending:
            picked = _resolve_pending_selection(pending, message)
            if picked is not None:
                try:
                    campaign_uuid = uuid.UUID(str(picked["campaign_id"]))
                except (ValueError, KeyError, TypeError):
                    campaign_uuid = None
                if campaign_uuid is not None:
                    row = (await db.execute(
                        select(RecruitmentCampaign, SpecificDateSlot)
                        .join(
                            SpecificDateSlot,
                            SpecificDateSlot.id
                            == RecruitmentCampaign.event_slot_id,
                        )
                        .where(
                            RecruitmentCampaign.id == campaign_uuid,
                            RecruitmentCampaign.tenant_id == tenant.id,
                        )
                    )).first()
                    if row is not None:
                        c, slot = row
                        type_ids = {
                            uuid.UUID(g["appointment_type_id"])
                            for g in (c.goals or [])
                            if g.get("appointment_type_id")
                        }
                        type_names: dict[str, str] = {}
                        if type_ids:
                            nq = await db.execute(
                                select(
                                    AppointmentType.id, AppointmentType.name
                                ).where(AppointmentType.id.in_(type_ids))
                            )
                            type_names = {
                                str(tid): name for tid, name in nq.all()
                            }
                        block = await _render_campaign_status_block(
                            db, c, slot, type_names
                        )
                        # Pending list consumed — clear so the next "1"
                        # isn't a stale shortcut to a different campaign.
                        await _clear_pending_status_list(
                            db, tenant.id, admin_id
                        )
                        return block

    if not _looks_like_status_query(message):
        return None

    # Relative-time short-circuit. "this week's status" / "today's status"
    # asks about the EVENTS in a time window, not the campaigns. Render
    # the per-event roll-up (one campaign block per event that has one,
    # one needs-and-signups block per event that doesn't). This avoids
    # the LLM hallucinating an unrelated campaign as the answer.
    relative_range = _extract_relative_date_range(message)
    if relative_range is not None:
        if admin_id is not None:
            await _clear_pending_status_list(db, tenant.id, admin_id)
        start, end = relative_range
        return await _render_events_in_range_block(db, tenant, start, end)

    # Pull all non-terminal campaigns + their slots
    q = await db.execute(
        select(RecruitmentCampaign, SpecificDateSlot)
        .join(
            SpecificDateSlot,
            SpecificDateSlot.id == RecruitmentCampaign.event_slot_id,
        )
        .where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.DRAFT,
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.ACTIVE,
                    CampaignStatus.PAUSED,
                ]
            ),
        )
        .order_by(SpecificDateSlot.date.asc())
    )
    rows = list(q.all())
    if not rows:
        if admin_id is not None:
            await _clear_pending_status_list(db, tenant.id, admin_id)
        return (
            "No recruitment campaigns are currently active or pending. "
            "Say 'plan recruitment for <event>' to start one."
        )

    # Optional event filter: extract date / label from the admin's text.
    # When this narrows the result we go straight to full-block render
    # (no numbered list needed — admin already named their event).
    filter_date, filter_label = _extract_status_filter(message)
    no_match_for_filter = False
    if filter_date or filter_label:
        filtered = _filter_campaigns_by_event(rows, filter_date, filter_label)
        if filtered:
            rows = filtered
        else:
            # Admin named a specific event but we found no campaign matching
            # it. Don't silently fall back to "the only other campaign" —
            # the admin would interpret that as the status of *their* event
            # and act on the wrong information. Flag and produce an honest
            # response below.
            no_match_for_filter = True

    # Service-name lookup (used only for the full-block path)
    type_ids = {
        uuid.UUID(g["appointment_type_id"])
        for c, _ in rows
        for g in (c.goals or [])
        if g.get("appointment_type_id")
    }
    type_names = {}
    if type_ids:
        nq = await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.id.in_(type_ids)
            )
        )
        type_names = {str(tid): name for tid, name in nq.all()}

    # Single campaign matching the admin's filter — full block.
    # Skip this fast-path when the filter found nothing; we want to be
    # honest about the miss instead of rendering an unrelated campaign.
    if len(rows) == 1 and not no_match_for_filter:
        c, slot = rows[0]
        block = await _render_campaign_status_block(db, c, slot, type_names)
        if admin_id is not None:
            await _clear_pending_status_list(db, tenant.id, admin_id)
        return block

    # Multiple campaigns (or filter missed) — show a short numbered list.
    # Persist for follow-up selection when we know which admin asked.
    if no_match_for_filter:
        # Admin named a specific event but no campaign exists. Try to
        # show the EVENT's current state (services needed + current
        # signups) — that's what the admin actually wants. Fall through
        # to the campaign listing only if we can't pin down a unique
        # event match.
        event_block = await _render_event_no_campaign_block(
            db, tenant, filter_date, filter_label
        )
        if event_block is not None:
            if admin_id is not None:
                await _clear_pending_status_list(db, tenant.id, admin_id)
            return event_block

        bits: list[str] = []
        if filter_label:
            bits.append(f"'{filter_label}'")
        if filter_date:
            bits.append(f"on {filter_date}")
        target = " ".join(bits) if bits else "that event"
        list_lines = [
            f"No active campaign or matching event found for {target}.",
            "",
            f"{len(rows)} active campaign(s):",
        ]
    else:
        list_lines = [f"{len(rows)} active campaign(s):"]

    entries_for_pending: list[dict] = []
    for idx, (c, slot) in enumerate(rows, start=1):
        label = slot.label or "event"
        event_date = slot.date.isoformat() if slot.date else "?"
        list_lines.append(
            f"{idx}. {label} — {event_date} [{c.status.value}]"
        )
        entries_for_pending.append({
            "campaign_id": str(c.id),
            "label": label,
            "date": event_date,
        })
    list_lines.append("")
    list_lines.append(
        "Reply with a number, event name, or date for details."
    )

    if admin_id is not None:
        await _save_pending_status_list(
            db, tenant.id, admin_id, entries_for_pending
        )

    return "\n".join(list_lines)


def _extract_status_filter(message: str) -> tuple[str | None, str | None]:
    """Pull a date and/or label out of a status query. Returns ``(None, None)``
    when no useful hint is found — caller then shows all campaigns.

    Strips status-trigger words ("status", "campaign", etc.) before label
    cleanup so phrases like "status of food drive campaign" don't leave
    "status" stuck on the label.
    """
    text = (message or "").strip().lower()
    if not text:
        return (None, None)
    # Trim trailing punctuation
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()

    iso_date, leftover = _extract_date_from_text(text)
    label_src = leftover if leftover else text
    # Strip status verbs from the label candidate; what's left is the
    # event reference (if any).
    status_noise = {
        "status", "of", "for", "the", "on", "campaign", "campaigns",
        "recruitment", "what", "is", "are", "how", "many", "any",
        "list", "show", "tell", "me", "about", "active", "running",
        "in", "progress", "happening", "ongoing", "current", "which",
        "where", "we", "stand", "doing",
    }
    tokens = [t for t in label_src.split() if t not in status_noise]
    cleaned = _clean_label(" ".join(tokens)) if tokens else ""
    if len(cleaned) < 3:
        cleaned = ""
    return (iso_date, cleaned or None)


def _filter_campaigns_by_event(
    rows: list,
    iso_date: str | None,
    label: str | None,
) -> list:
    """Narrow a (campaign, slot) row list to ones matching date + label.

    Date match is exact (campaign event_date == iso_date). Label match
    is case-insensitive substring on slot.label. When both are given we
    AND them. When neither produces a match we return [] and the caller
    falls back to "show all" (over-showing beats hiding what they want).
    """
    out = []
    for c, slot in rows:
        if iso_date:
            if not slot.date or slot.date.isoformat() != iso_date:
                continue
        if label:
            slot_label = (slot.label or "").lower()
            if label.lower() not in slot_label:
                continue
        out.append((c, slot))
    return out


# ── Pending status-selection state ────────────────────────────────
#
# An admin's "status of campaigns" query (with no event filter) returns
# a short numbered list rather than dumping every campaign's full block —
# SMS would be too long to scan. The admin then replies with a number,
# event name, or date to pick which one to expand. That follow-up reply
# is a SHORT, contextless message ("1", "awareness seminar", "Jul 4") so
# we persist the offered list per-admin and resolve the next reply
# against it.
#
# Storage: per-tenant SystemSetting row keyed by admin id; value is a
# JSON blob with a TTL we enforce on read. Avoids new tables for what's
# effectively a 10-minute breadcrumb.

_PENDING_STATUS_TTL_SECONDS = 600
_PENDING_STATUS_KEY_PREFIX = "pending_status_list_"
_NUMERIC_SELECTION_RE = re.compile(r"^\s*#?\s*(\d{1,2})\s*$")


def _pending_status_key(admin_id: uuid.UUID) -> str:
    return f"{_PENDING_STATUS_KEY_PREFIX}{admin_id}"


async def _save_pending_status_list(
    db,
    tenant_id: uuid.UUID,
    admin_id: uuid.UUID,
    entries: list[dict],
) -> None:
    """Persist {campaign_id, label, date} list so a follow-up selection
    reply can resolve back to a campaign without re-running the query."""
    from datetime import datetime, timezone

    from app.models.system_setting import SystemSetting

    key = _pending_status_key(admin_id)
    payload = json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    })
    existing = (await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == key,
        )
    )).scalar_one_or_none()
    if existing:
        existing.value = payload
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSetting(tenant_id=tenant_id, key=key, value=payload))
    await db.flush()


async def _load_pending_status_list(
    db,
    tenant_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> list[dict] | None:
    """Return the saved list if it's still within TTL, else None."""
    from datetime import datetime, timedelta, timezone

    from app.models.system_setting import SystemSetting

    row = (await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == _pending_status_key(admin_id),
        )
    )).scalar_one_or_none()
    if row is None:
        return None
    try:
        payload = json.loads(row.value or "{}")
        created = datetime.fromisoformat(payload.get("created_at", ""))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    if datetime.now(timezone.utc) - created > timedelta(
        seconds=_PENDING_STATUS_TTL_SECONDS
    ):
        return None
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        return None
    return entries


async def _clear_pending_status_list(
    db,
    tenant_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    from sqlalchemy import delete as sql_delete
    from app.models.system_setting import SystemSetting

    await db.execute(
        sql_delete(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == _pending_status_key(admin_id),
        )
    )
    await db.flush()


def _resolve_pending_selection(
    entries: list[dict],
    message: str,
) -> dict | None:
    """Match a follow-up reply against the saved list.

    Order of attempts:
      1. Ordinal — "1", "2", "#3" (1-indexed against the list)
      2. ISO date or date-extraction match against entry["date"]
      3. Case-insensitive label substring match

    Returns the matched entry, or None if nothing resolves
    unambiguously (multiple matches on label also returns None — the
    admin has to disambiguate).
    """
    text = (message or "").strip().lower()
    if not text:
        return None

    m = _NUMERIC_SELECTION_RE.match(text)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(entries):
            return entries[idx]
        return None

    iso_date, leftover = _extract_date_from_text(text)
    if iso_date:
        matches = [e for e in entries if e.get("date") == iso_date]
        if len(matches) == 1:
            return matches[0]
        # Multiple events on the same date — fall through and try label.

    candidate_label = (leftover or text).strip()
    candidate_label = _clean_label(candidate_label)
    if len(candidate_label) >= 3:
        lc = candidate_label.lower()
        matches = [e for e in entries if lc in (e.get("label") or "").lower()]
        if len(matches) == 1:
            return matches[0]
    return None


def _fmt_short_date(dt) -> str:
    """Return 'Jun 1' / 'May 25' — portable across Windows (%-d isn't)."""
    if not dt:
        return "?"
    return f"{dt.strftime('%b')} {dt.day}"


def _extract_relative_date_range(message: str) -> tuple[date, date] | None:
    """Detect relative time-window phrases and return an inclusive date
    range. Returns None when no phrase matches.

    Supported:
      today, tomorrow         -> single-day range
      this week, next week    -> Monday..Sunday (ISO week)
      this month, next month  -> 1st..last of month
      next 7 days             -> today..today+6

    Checked before the explicit YYYY-MM-DD / month-name extractor so
    "this week" wins over a chance digit match.
    """
    from datetime import timedelta

    text = (message or "").lower()
    if not text:
        return None
    today = date.today()

    if "tomorrow" in text:
        t = today + timedelta(days=1)
        return (t, t)
    if "today" in text:
        return (today, today)
    if "this week" in text:
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return (monday, sunday)
    if "next week" in text:
        next_monday = today + timedelta(days=(7 - today.weekday()))
        next_sunday = next_monday + timedelta(days=6)
        return (next_monday, next_sunday)
    if "this month" in text:
        from calendar import monthrange
        last_day = monthrange(today.year, today.month)[1]
        return (today.replace(day=1), today.replace(day=last_day))
    if "next month" in text:
        from calendar import monthrange
        if today.month == 12:
            year, month = today.year + 1, 1
        else:
            year, month = today.year, today.month + 1
        last_day = monthrange(year, month)[1]
        return (date(year, month, 1), date(year, month, last_day))
    if "next 7 days" in text or "next seven days" in text:
        return (today, today + timedelta(days=6))
    return None


async def _render_events_in_range_block(
    db,
    tenant: Tenant,
    start: date,
    end: date,
) -> str:
    """Multi-event status for a date range. Used when the admin asks
    'this week's status' / 'what's happening tomorrow' etc.

    For each event in the range:
      - If a campaign exists -> render the full campaign block
      - Otherwise -> render the event's needs + current signups

    When there are no events at all in the range, returns a short
    'no events scheduled' message.
    """
    from app.agents.recruiter.executor import current_signups_per_service
    from app.models.appointment_type import AppointmentType
    from app.models.availability import SpecificDateSlot

    eq = await db.execute(
        select(SpecificDateSlot)
        .where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date >= start,
            SpecificDateSlot.date <= end,
        )
        .order_by(SpecificDateSlot.date.asc())
    )
    events = list(eq.scalars().all())

    range_label = (
        start.isoformat() if start == end
        else f"{start.isoformat()} to {end.isoformat()}"
    )

    if not events:
        return f"No events scheduled for {range_label}."

    # Pull campaigns attached to any of these events.
    slot_ids = [s.id for s in events]
    cq = await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.event_slot_id.in_(slot_ids),
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.DRAFT,
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.ACTIVE,
                    CampaignStatus.PAUSED,
                ]
            ),
        )
    )
    campaigns_by_slot: dict[uuid.UUID, RecruitmentCampaign] = {}
    for c in cq.scalars().all():
        campaigns_by_slot[c.event_slot_id] = c

    # Collect every service id referenced (event needs + campaign goals)
    # so we can do one batched name lookup.
    all_service_ids: set[uuid.UUID] = set()
    for slot in events:
        for g in slot.service_config or []:
            sid = g.get("appointment_type_id")
            if sid:
                try:
                    all_service_ids.add(uuid.UUID(sid))
                except (ValueError, TypeError):
                    pass
    type_names: dict[str, str] = {}
    if all_service_ids:
        nq = await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.id.in_(list(all_service_ids))
            )
        )
        type_names = {str(tid): name for tid, name in nq.all()}

    # Render per-event blocks.
    blocks: list[str] = [f"Status for {range_label}: {len(events)} event(s)"]
    for slot in events:
        camp = campaigns_by_slot.get(slot.id)
        if camp is not None:
            blocks.append("")
            blocks.append(
                await _render_campaign_status_block(db, camp, slot, type_names)
            )
            continue

        # No campaign — render the event's needs + signups.
        service_config = slot.service_config or []
        service_ids = [
            uuid.UUID(g["appointment_type_id"])
            for g in service_config
            if g.get("appointment_type_id")
        ]
        signups = (
            await current_signups_per_service(db, slot, service_ids)
            if service_ids else {}
        )

        def _min_of(g: dict) -> int:
            return int(g.get("min_required") or 0)

        total_signed = sum(int(signups.get(sid, 0)) for sid in signups)
        total_min = sum(_min_of(g) for g in service_config)
        needed = max(0, total_min - total_signed)
        needed_part = (
            f" ({needed} more needed)" if total_min > 0 and needed > 0
            else " (target hit)" if total_min > 0
            else ""
        )

        label = slot.label or "event"
        event_date = slot.date.isoformat() if slot.date else "?"
        block_lines = [
            "",
            f"**{label}** — {event_date} [no campaign yet]",
            f"Total: {total_signed} of {total_min} signed up{needed_part}",
        ]
        if service_config:
            block_lines.append("Volunteer needs:")
            for g in service_config:
                sid_raw = g.get("appointment_type_id")
                if not sid_raw:
                    continue
                name = type_names.get(sid_raw, "service")
                sg = int(signups.get(sid_raw, 0))
                mn = _min_of(g)
                if mn > 0:
                    svc_needed = max(0, mn - sg)
                    svc_needed_part = (
                        f" ({svc_needed} more needed)" if svc_needed > 0
                        else " (target hit)"
                    )
                else:
                    svc_needed_part = ""
                block_lines.append(f"  • {name} — {sg}/{mn}{svc_needed_part}")
        blocks.extend(block_lines)

    return "\n".join(blocks)


async def _render_event_no_campaign_block(
    db,
    tenant: Tenant,
    filter_date: str | None,
    filter_label: str | None,
) -> str | None:
    """Look up the event itself when no campaign matches.

    Used by the status flow's miss-path: admin named a specific event,
    no campaign exists for it. If the EVENT exists, render its current
    state — services needed, signups so far, and the suggested next
    action. Returns None when 0 or >1 events match (caller falls back
    to listing active campaigns so the admin can still get unstuck).
    """
    from datetime import date as _date

    from app.agents.recruiter.executor import current_signups_per_service
    from app.models.appointment_type import AppointmentType
    from app.models.availability import SpecificDateSlot

    if not (filter_date or filter_label):
        return None

    q = select(SpecificDateSlot).where(
        SpecificDateSlot.tenant_id == tenant.id,
        SpecificDateSlot.is_active.is_(True),
    )
    if filter_date:
        try:
            q = q.where(SpecificDateSlot.date == _date.fromisoformat(filter_date))
        except ValueError:
            return None
    if filter_label:
        # ILIKE so the substring match is case-insensitive and runs in PG.
        q = q.where(SpecificDateSlot.label.ilike(f"%{filter_label}%"))

    rows = list(
        (await db.execute(q.order_by(SpecificDateSlot.date.asc()))).scalars().all()
    )
    if len(rows) != 1:
        return None

    slot = rows[0]
    service_config = slot.service_config or []
    service_ids: list[uuid.UUID] = []
    for g in service_config:
        sid_raw = g.get("appointment_type_id")
        if not sid_raw:
            continue
        try:
            service_ids.append(uuid.UUID(sid_raw))
        except (ValueError, TypeError):
            continue

    type_names: dict[str, str] = {}
    if service_ids:
        nq = await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.id.in_(service_ids)
            )
        )
        type_names = {str(tid): name for tid, name in nq.all()}

    signups = (
        await current_signups_per_service(db, slot, service_ids)
        if service_ids else {}
    )

    def _min_of(g: dict) -> int:
        return int(g.get("min_required") or 0)

    total_signed = sum(int(signups.get(sid, 0)) for sid in signups)
    total_min = sum(_min_of(g) for g in service_config)
    needed = max(0, total_min - total_signed)

    label = slot.label or "event"
    event_date = slot.date.isoformat() if slot.date else "?"

    if total_min > 0:
        needed_part = (
            f" ({needed} more needed)" if needed > 0 else " (target hit)"
        )
    else:
        needed_part = ""

    lines = [
        f"**{label}** — {event_date} [no campaign yet]",
        f"Total: {total_signed} of {total_min} signed up{needed_part}",
    ]

    if service_config:
        lines.append("")
        lines.append("Volunteer needs:")
        for g in service_config:
            sid_raw = g.get("appointment_type_id")
            if not sid_raw:
                continue
            name = type_names.get(sid_raw, "service")
            sg = int(signups.get(sid_raw, 0))
            mn = _min_of(g)
            if mn > 0:
                svc_needed = max(0, mn - sg)
                svc_needed_part = (
                    f" ({svc_needed} more needed)" if svc_needed > 0
                    else " (target hit)"
                )
            else:
                svc_needed_part = ""
            lines.append(f"  • {name} — {sg}/{mn}{svc_needed_part}")
    else:
        lines.append("")
        lines.append("(No service requirements configured for this event.)")

    lines.append("")
    lines.append(
        f"No active recruitment campaign for this event. "
        f"Say 'plan recruitment for {label}' to start one."
    )

    return "\n".join(lines)


async def _render_campaign_status_block(
    db,
    campaign: RecruitmentCampaign,
    slot,
    type_names: dict[str, str],
) -> str:
    """Render one campaign as a multi-line status block:

      **<event>** — <date> [<status>]
      Total: X of Y signed up (Z more needed)

      By service:
        • <service> — X/Y (Z more needed)

      Waves:
        • Wave N sent <date> — <sent_count> contacted, <signups_attributed> signups
        • Next: Wave M scheduled for <date>
    """
    from app.agents.recruiter.executor import current_signups_per_service
    from datetime import datetime, timezone

    service_ids = [
        uuid.UUID(g["appointment_type_id"])
        for g in campaign.goals or []
        if g.get("appointment_type_id")
    ]
    signups = await current_signups_per_service(db, slot, service_ids)

    def _min_of(g: dict) -> int:
        if g.get("min_required") is not None:
            return int(g.get("min_required") or 0)
        return int(g.get("target") or 0)

    total_signed = sum(int(signups.get(sid, 0)) for sid in signups)
    total_min = sum(_min_of(g) for g in campaign.goals or [])
    needed = max(0, total_min - total_signed)

    label = slot.label or "event"
    event_date = slot.date.isoformat() if slot.date else "?"
    needed_part = (
        f" ({needed} more needed)" if needed > 0
        else " (target hit)"
    )
    lines = [
        f"**{label}** — {event_date} [{campaign.status.value}]",
        f"Total: {total_signed} of {total_min} signed up{needed_part}",
        "",
        "By service:",
    ]

    if not campaign.goals:
        lines.append("  • (no services configured)")
    else:
        for g in campaign.goals:
            sid = g.get("appointment_type_id")
            if not sid:
                continue
            name = type_names.get(sid, "service")
            sg = int(signups.get(sid, 0))
            mn = _min_of(g)
            svc_needed = max(0, mn - sg)
            svc_needed_part = (
                f" ({svc_needed} more needed)" if svc_needed > 0
                else " (target hit)"
            )
            lines.append(f"  • {name} — {sg}/{mn}{svc_needed_part}")

    # Wave history + next scheduled wave.
    # Waves are stored per (wave_number, appointment_type_id) — i.e. one row
    # per service inside each wave. The admin thinks in terms of waves, not
    # per-service shards, so group by wave_number and roll up sent_count +
    # signups_attributed across the services. Use the earliest scheduled_at
    # in the group as the wave's "sent" date (all per-service shards of a
    # wave are scheduled together; they may differ by milliseconds).
    waves_q = await db.execute(
        select(RecruitmentWave)
        .where(RecruitmentWave.campaign_id == campaign.id)
        .order_by(RecruitmentWave.wave_number.asc())
    )
    waves = list(waves_q.scalars().all())
    if waves:
        lines.append("")
        lines.append("Waves:")
        now = datetime.now(timezone.utc)
        # Group by wave_number → roll up SENT shards.
        from collections import defaultdict
        sent_groups: dict[int, list] = defaultdict(list)
        planned_groups: dict[int, list] = defaultdict(list)
        for w in waves:
            if w.status == WaveStatus.SENT:
                sent_groups[w.wave_number].append(w)
            elif (
                w.status == WaveStatus.PLANNED
                and w.scheduled_at and w.scheduled_at > now
            ):
                planned_groups[w.wave_number].append(w)

        for wave_num in sorted(sent_groups.keys()):
            shards = sent_groups[wave_num]
            sent_dates = [w.scheduled_at for w in shards if w.scheduled_at]
            when = _fmt_short_date(min(sent_dates)) if sent_dates else "?"
            total_contacted = sum(w.sent_count or 0 for w in shards)
            total_signups = sum(w.signups_attributed or 0 for w in shards)
            attributed = (
                f", {total_signups} signups" if total_signups else ""
            )
            lines.append(
                f"  • Wave {wave_num} sent {when} — "
                f"{total_contacted} contacted{attributed}"
            )

        if planned_groups:
            next_num = min(planned_groups.keys())
            shards = planned_groups[next_num]
            when_dates = [w.scheduled_at for w in shards if w.scheduled_at]
            when = _fmt_short_date(min(when_dates)) if when_dates else "?"
            lines.append(
                f"  • Next: Wave {next_num} scheduled for {when}"
            )
        elif not sent_groups:
            # No sent + no upcoming — likely awaiting approval.
            lines.append("  • No waves sent yet")

    return "\n".join(lines)


async def build_admin_state_preamble(
    db,
    tenant: Tenant,
    admin_user: AdminUser | None,
) -> str:
    """Return a compact "CURRENT SYSTEM STATE" block to inject into the
    admin system prompt.

    The LLM keeps the conversation history (so admin gets continuity)
    but every turn also sees the latest authoritative facts so it can't
    parrot stale information (e.g., "no phone configured" after the
    phone was set, or "campaign approved" when none exists).

    Kept under ~300 tokens. Queries are cheap (4 small SELECTs).
    """
    from datetime import date, datetime, timezone, timedelta
    from sqlalchemy import func
    from app.models.availability import SpecificDateSlot

    today = date.today()

    # 1. Admin identity + phone status
    if admin_user:
        admin_line = f"- Logged-in admin: {admin_user.email}"
        if admin_user.phone:
            p = admin_user.phone
            masked = p[:3] + "***" + p[-4:] if len(p) >= 7 else p
            phone_line = (
                f"- Admin SMS phone: CONFIGURED ({masked}) — recruitment "
                "plans and reports go via SMS AND dashboard"
            )
        else:
            phone_line = (
                "- Admin SMS phone: NOT configured — recruitment plans "
                "and reports go via dashboard Notifications only (no SMS)"
            )
    else:
        admin_line = "- Logged-in admin: unknown"
        phone_line = "- Admin SMS phone: unknown"

    # 2. Campaign counts
    active_q = await db.execute(
        select(func.count(RecruitmentCampaign.id)).where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status == CampaignStatus.ACTIVE,
        )
    )
    active_n = int(active_q.scalar() or 0)
    pending_q = await db.execute(
        select(func.count(RecruitmentCampaign.id)).where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status == CampaignStatus.AWAITING_APPROVAL,
        )
    )
    pending_n = int(pending_q.scalar() or 0)

    # 3. Upcoming events — INCLUDES recurring rules (next occurrence)
    #    so the LLM doesn't answer "list events" from memory and skip
    #    the weekly programs. One-off events: 60-day horizon. Recurring:
    #    one entry per active rule, showing next occurrence date. Both
    #    are HINTS — for full volunteer counts the LLM should call
    #    manage_specific_date_slot action='list' (which returns much
    #    richer per-event detail).
    from app.models.availability import AvailabilityRule
    cutoff = today + timedelta(days=60)
    ev_q = await db.execute(
        select(SpecificDateSlot)
        .where(
            SpecificDateSlot.tenant_id == tenant.id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date >= today,
            SpecificDateSlot.date <= cutoff,
        )
        .order_by(SpecificDateSlot.date.asc())
        .limit(8)
    )
    one_off_events = list(ev_q.scalars().all())

    rules_q = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.tenant_id == tenant.id,
            AvailabilityRule.is_active.is_(True),
        )
    )
    rules = list(rules_q.scalars().all())

    parts: list[str] = []
    for s in one_off_events:
        parts.append(f"{s.label or 'event'} ({s.date.isoformat()})")
    _day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for r in rules:
        days_ahead = (r.day_of_week - today.weekday()) % 7
        next_date = (today + timedelta(days=days_ahead)).isoformat()
        recur_str = (
            f"weekly {_day_names[r.day_of_week]}"
            if r.day_of_week is not None and 0 <= r.day_of_week < 7
            else "weekly"
        )
        parts.append(
            f"{r.label or 'recurring program'} (next {next_date}, {recur_str})"
        )
    ev_str = "; ".join(parts) if parts else "none"
    counts_str = (
        f"{len(one_off_events)} one-off, {len(rules)} recurring"
        if (one_off_events or rules) else "none"
    )

    return (
        "=== CURRENT SYSTEM STATE — AUTHORITATIVE, OVERRIDES ANY "
        "CONFLICTING INFORMATION IN CONVERSATION HISTORY ===\n"
        f"- Today: {today.isoformat()}\n"
        f"{admin_line}\n"
        f"{phone_line}\n"
        f"- Active recruitment campaigns: {active_n}\n"
        f"- Campaigns awaiting your approval: {pending_n}\n"
        f"- Upcoming events ({counts_str}): {ev_str}\n"
        "=== END CURRENT STATE ===\n"
        "If the conversation history says something that contradicts "
        "the above (e.g., \"your account has no SMS configured\" when "
        "the state above says CONFIGURED), the state above wins. Trust "
        "the current state, not the history.\n"
        "\n"
        "EVENT-LIST QUERIES: The state above shows event LABELS + DATES "
        "only. When the admin asks to list events / see what's coming up / "
        "show upcoming events, you MUST call manage_specific_date_slot "
        "with action='list' to get the FULL data: per-event volunteer "
        "summary (total_needed / total_signed_up / more_required), "
        "per-service breakdown, location, time, recurrence label, etc. "
        "Do NOT answer event-list questions from the state block above — "
        "it lacks signups and service detail and the admin specifically "
        "needs those numbers.\n"
    )


# Lookback window for finding the wave that solicited this contact. 48h
# matches the default cooldown_hours_within_campaign — beyond that we
# assume any "yes" reply is unrelated to recent recruitment outreach.
PENDING_SOLICITATION_LOOKBACK_HOURS = 48


async def get_pending_solicitation(
    db,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID | None,
    lookback_hours: int = PENDING_SOLICITATION_LOOKBACK_HOURS,
) -> dict | None:
    """Find the most recent recruitment wave that targeted this contact.

    Returns the service + event the volunteer was solicited for so the
    customer LLM can resolve ambiguous "yes" / "sign me up" replies to
    the *correct* service — not a same-named one elsewhere in the tenant.

    Fixes the class of bug where the outbound SMS mentions only the
    event label (e.g., "Food Drive") but the wave actually targets a
    different service (e.g., "Parking lot supervision") that this
    volunteer is eligible for. Without this lookup, the LLM had to guess
    from message text alone and would pick the wrong service whenever
    the event and a service shared a name.
    """
    if not contact_id:
        return None

    from datetime import datetime, timedelta, timezone

    from app.models.appointment_type import AppointmentType
    from app.models.availability import SpecificDateSlot

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    cid_str = str(contact_id)

    # JSONB containment: targeted_contact_ids is a list of UUID strings.
    # Using `?` operator via SQLAlchemy's func.jsonb_exists keeps this an
    # index-friendly check on Postgres. Fallback to row scan is fine —
    # the SENT-wave-within-48h population is small per tenant.
    waves_q = await db.execute(
        select(RecruitmentWave)
        .where(
            RecruitmentWave.tenant_id == tenant_id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= cutoff,
        )
        .order_by(RecruitmentWave.scheduled_at.desc())
    )
    waves = list(waves_q.scalars().all())
    wave = next(
        (
            w for w in waves
            if w.targeted_contact_ids
            and any(str(x) == cid_str for x in w.targeted_contact_ids)
        ),
        None,
    )
    if wave is None:
        return None

    campaign = await db.get(RecruitmentCampaign, wave.campaign_id)
    if campaign is None:
        return None
    slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
    appt_type = await db.get(AppointmentType, wave.appointment_type_id)
    if slot is None or appt_type is None:
        return None

    return {
        "wave_id": str(wave.id),
        "campaign_id": str(campaign.id),
        "service_id": str(appt_type.id),
        "service_name": appt_type.name,
        "event_slot_id": str(slot.id),
        "event_label": slot.label or appt_type.name,
        "event_date": slot.date.isoformat() if slot.date else "",
        "event_start_time": slot.start_time.strftime("%H:%M")
        if slot.start_time
        else "",
        "event_end_time": slot.end_time.strftime("%H:%M")
        if slot.end_time
        else "",
        "event_location": slot.location or "",
        "sent_at": wave.scheduled_at.isoformat() if wave.scheduled_at else "",
    }


def _humanize_hours_ago(sent_iso: str) -> str:
    """Render an ISO timestamp as a short relative span."""
    from datetime import datetime, timezone

    if not sent_iso:
        return "recently"
    try:
        sent = datetime.fromisoformat(sent_iso)
    except (TypeError, ValueError):
        return "recently"
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - sent
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "moments ago"
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


async def _roster_visibility_block(
    db,
    contact_id: uuid.UUID | None,
    tenant_id: uuid.UUID | None = None,
) -> str | None:
    """Render the volunteer's saved roster-visibility default — or, when no
    default is saved, instruct the LLM to ASK ONCE and let book_appointment
    persist the answer. Returns None when contact_id is None (admin sender).

    The actual prompt bodies (saved + unset variants) live in
    app/prompts/conversation.py and are UI-editable via the AI Prompts
    page so admins can adjust wording / interpretation rules per-tenant.
    This helper just resolves the dynamic substitutions (name, choice
    labels) and picks which prompt to inject.
    """
    if contact_id is None:
        return None
    from app.models.contact import Contact as _Contact
    from app.prompts.conversation import (
        get_customer_roster_saved_prompt,
        get_customer_roster_unset_prompt,
    )

    row = (
        await db.execute(
            select(_Contact.default_roster_visibility, _Contact.name).where(
                _Contact.id == contact_id
            )
        )
    ).first()
    if row is None:
        return None
    saved_visibility, name = row
    full_name = (name or "").strip() or None
    first_name = full_name.split()[0] if full_name else None
    label_map = {
        "first_name": (
            f"first name only ({first_name})"
            if first_name else "first name only"
        ),
        "full_name": (
            f"full name ({full_name})"
            if full_name else "full name"
        ),
        "hidden": "hidden (not shown to other volunteers)",
    }
    if saved_visibility in label_map:
        template = await get_customer_roster_saved_prompt(db, tenant_id)
        return template.replace("{saved_display}", label_map[saved_visibility])

    # No saved default — instruct the LLM to ask once.
    template = await get_customer_roster_unset_prompt(db, tenant_id)
    first_name_choice = f"({first_name})" if first_name else "(default)"
    full_name_choice = f"({full_name})" if full_name else ""
    return (
        template
        .replace("{first_name_choice}", first_name_choice)
        .replace("{full_name_choice}", full_name_choice)
    )


async def _pending_reconfirm_block(
    db, tenant: Tenant, contact_id: uuid.UUID
) -> str | None:
    """Render a preamble block for any pending event-reschedule
    reconfirmations for this contact, or None when there are none.

    A server-side intent router in [services/reconfirm.py] catches
    bare YES / STOP replies, so this block is the "fall-through"
    guidance for less-trivial replies ("can I come at noon instead?",
    "does that include parking duty too?", "wait, what changed?").
    """
    from app.services.reconfirm import pending_reconfirmations
    pending = await pending_reconfirmations(db, tenant.id, contact_id)
    if not pending:
        return None

    lines = []
    for booking in pending[:3]:  # cap to keep prompt small
        when = booking.scheduled_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"- Booking at {when} (id ending {str(booking.id)[-8:]})")
    bullets = "\n".join(lines)
    return (
        "=== PENDING EVENT RECONFIRMATION — AUTHORITATIVE CONTEXT ===\n"
        "This volunteer received an SMS about an event they signed up "
        "for being rescheduled. They have not yet confirmed or opted out.\n"
        f"{bullets}\n"
        "\n"
        "Rules:\n"
        "1. Bare YES / STOP replies are handled by a server-side router "
        "BEFORE this LLM call, so if you're seeing this message it's "
        "because the volunteer wrote something more nuanced.\n"
        "2. If the volunteer is asking a question or expressing concern "
        "about the new date/time, answer it; do NOT auto-confirm or "
        "auto-cancel.\n"
        "3. If they want to opt out via a non-trigger phrase (e.g., "
        "\"I won't make it\", \"please remove me\"), use the existing "
        "cancel_booking tool with their booking reference.\n"
        "4. If they want to keep but reschedule to ANOTHER time, use the "
        "reschedule_booking tool, not the reconfirmation flow.\n"
        "=== END PENDING RECONFIRMATION ===\n"
    )


async def _my_existing_bookings_block(
    db,
    tenant: Tenant,
    contact_id: uuid.UUID,
) -> str | None:
    """Render the volunteer's own upcoming non-cancelled bookings so
    the LLM can tell "you're already signed up for X at this time"
    apart from "someone else has reserved a slot at this time" —
    the latter is capacity/who_signed_up info and is NOT a conflict
    for this volunteer.

    Without this block the LLM was reading the `who_signed_up` array
    on a check_availability response and treating other volunteers'
    names as if they were the current volunteer's own bookings,
    leading to spurious "you can't do both" overlap warnings.

    Returns None when the volunteer has no upcoming bookings.
    """
    from datetime import datetime, timedelta, timezone

    import pytz

    from app.models.appointment_type import AppointmentType
    from app.models.availability import SpecificDateSlot
    from app.models.booking import Booking, BookingStatus

    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(Booking, AppointmentType, SpecificDateSlot)
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .outerjoin(
            SpecificDateSlot,
            SpecificDateSlot.id == Booking.event_slot_id,
        )
        .where(
            Booking.tenant_id == tenant.id,
            Booking.contact_id == contact_id,
            Booking.status.in_([
                BookingStatus.SCHEDULED,
                BookingStatus.RESCHEDULED,
            ]),
            Booking.scheduled_at >= now,
        )
        .order_by(Booking.scheduled_at.asc())
        .limit(10)
    )).all()
    if not rows:
        return None

    try:
        tz = pytz.timezone(tenant.business_timezone or "UTC")
    except Exception:
        tz = pytz.UTC

    lines: list[str] = []
    for booking, appt, slot in rows:
        local = booking.scheduled_at.astimezone(tz)
        duration = timedelta(minutes=appt.duration_minutes or 0)
        end_local = (booking.scheduled_at + duration).astimezone(tz)
        when = local.strftime("%a %b %d %Y, %I:%M %p")
        end_str = end_local.strftime("%I:%M %p")
        event_label = (slot.label if slot is not None else None) or "(recurring window)"
        location = (slot.location if slot is not None else None) or "TBD"
        lines.append(
            f"- {appt.name} at {event_label} on {when}–{end_str} ({location})"
        )

    return (
        "=== MY EXISTING BOOKINGS (this volunteer's own commitments) ===\n"
        "These are the bookings THIS volunteer has already made. Use this "
        "list — and ONLY this list — to detect 'you're already signed up' "
        "overlaps before calling book_appointment. The who_signed_up array "
        "on check_availability shows OTHER volunteers and is NOT a conflict "
        "for this volunteer.\n"
        + "\n".join(lines)
        + "\n=== END MY EXISTING BOOKINGS ===\n"
    )


async def build_customer_state_preamble(
    db,
    tenant: Tenant,
    contact_id: uuid.UUID | None,
) -> str | None:
    """Return the CURRENT VOLUNTEER STATE preamble, or None if nothing to add.

    Composes (in order) any of:
      - pending recruitment solicitation (decision #18)
      - pending event reconfirmation (decision #19)
    Returns None when both are absent so the caller can skip the
    append cleanly.
    """
    blocks: list[str] = []

    if contact_id is not None:
        reconfirm_block = await _pending_reconfirm_block(db, tenant, contact_id)
        if reconfirm_block:
            blocks.append(reconfirm_block)

        existing_block = await _my_existing_bookings_block(
            db, tenant, contact_id
        )
        if existing_block:
            blocks.append(existing_block)

    # Roster-visibility default: surface the volunteer's saved preference (if
    # any) so the booking-flow rules know whether to ASK or to proceed
    # silently. Without this block the LLM either re-asks on every booking
    # (annoying) or auto-defaults to first_name (silent — what this whole
    # thread is trying to avoid).
    roster_block = await _roster_visibility_block(db, contact_id, tenant.id)
    if roster_block:
        blocks.append(roster_block)

    pending = await get_pending_solicitation(db, tenant.id, contact_id)
    if pending is not None:
        sent_ago = _humanize_hours_ago(pending.get("sent_at", ""))
        when = pending.get("event_date", "")
        start = pending.get("event_start_time", "")
        end = pending.get("event_end_time", "")
        window = (
            f"{start} to {end}" if start and end
            else (start or "the scheduled time")
        )
        location = pending.get("event_location") or "the event location"
        svc = pending["service_name"]
        label = pending["event_label"]
        blocks.append(
            "=== PENDING RECRUITMENT SOLICITATION — AUTHORITATIVE CONTEXT ===\n"
            "This volunteer received a recruitment SMS asking them to fill "
            "a specific service at a specific event. Treat the details below "
            "as the ground truth for any sign-up reply.\n"
            f"- Service to book: {svc}\n"
            f"- Event: {label} on {when} ({window}, {location})\n"
            f"- Sent: {sent_ago}\n"
            "\n"
            "Rules:\n"
            "1. If the volunteer replies with a YES-style confirmation "
            "(\"yes\", \"sure\", \"ok\", \"sign me up\", \"i'll do it\", "
            "\"count me in\", etc.) WITHOUT naming a different service, "
            "follow the ROSTER VISIBILITY block above: if they already "
            "have a saved default, send ONE short confirmation reply "
            f"(\"Great! That's for {svc} at {label} on {when} — booking "
            "now.\") and call book_appointment WITHOUT share_on_roster "
            f"(args: appointment_type_name=\"{svc}\", date=\"{when}\", "
            f"time=\"{start}\"). If they have no saved default, send "
            "ONE short reply that (a) confirms the service explicitly "
            "AND (b) asks how they want to appear on the roster, then "
            "wait for their answer and call book_appointment with the "
            "chosen share_on_roster. Never book silently and never "
            "re-ask the roster question when a saved default exists.\n"
            "2. The service name above is authoritative. The outbound SMS "
            "may have referred to the event by its label (which can collide "
            "with a same-named service elsewhere) — IGNORE that ambiguity "
            "and book the service named above.\n"
            "3. If the volunteer explicitly names a DIFFERENT service, "
            "follow what they said (still ask about roster visibility "
            "before booking).\n"
            "4. If the volunteer declines, asks a question, or reports a "
            "scheduling conflict, handle normally — do not force-book.\n"
            "=== END PENDING SOLICITATION ===\n"
        )

    return "\n".join(blocks) if blocks else None


async def handle_delete_recruitment_campaign(
    ctx: ToolContext, tool_input: dict
) -> str:
    """Delete a recruitment campaign + cascade its waves/signups/reports.

    Destructive. Mirrors api/recruitment.py::delete_campaign:
      - PLANNED waves get cancelled before delete so the tick loop won't
        try to re-fire mid-delete
      - Announcements linked to this campaign's waves get their
        recruitment_wave_id NULL'd (the FK was created without ON DELETE
        SET NULL, so cascading would fail otherwise; past SMS audit is
        preserved this way)
      - Campaign row hard-deleted; recruitment_signups + recruitment_reports
        cascade-delete via their own FK ON DELETE CASCADE

    Resolution input shape:
      - campaign_id (UUID string) — if present, use directly
      - event_date (YYYY-MM-DD) and/or event_label — to look up the
        campaign(s) attached to that event slot

    Returns needs_clarification when multiple campaigns match, so the
    admin (or LLM) can pick.
    """
    if not ctx.is_admin:
        return json.dumps({"error": "Recruitment is an admin-only feature."})

    from app.models.announcement import Announcement
    from sqlalchemy import update

    # Resolve target campaign(s)
    target_campaign_id_raw = tool_input.get("campaign_id")
    target_campaign: RecruitmentCampaign | None = None

    if target_campaign_id_raw:
        try:
            cid = uuid.UUID(str(target_campaign_id_raw))
        except (ValueError, TypeError):
            return json.dumps({"error": "Invalid campaign_id format."})
        target_campaign = await ctx.db.get(RecruitmentCampaign, cid)
        if (
            target_campaign is None
            or target_campaign.tenant_id != ctx.tenant.id
        ):
            return json.dumps({"error": "Campaign not found."})
    else:
        # Resolve via event slot — same _resolve_event_slot helper the
        # start handler uses, then filter campaigns attached to it.
        slot, clarification = await _resolve_event_slot(
            ctx,
            event_date_str=tool_input.get("event_date"),
            event_label=tool_input.get("event_label"),
        )
        if clarification is not None:
            return json.dumps(clarification)
        assert slot is not None

        # All campaigns (any status) for this slot. If multiple exist
        # for the same slot — unusual but possible if an old completed
        # campaign coexists with a new active one — ask which.
        q = await ctx.db.execute(
            select(RecruitmentCampaign)
            .where(
                RecruitmentCampaign.tenant_id == ctx.tenant.id,
                RecruitmentCampaign.event_slot_id == slot.id,
            )
            .order_by(desc(RecruitmentCampaign.updated_at))
        )
        campaigns = list(q.scalars().all())
        if not campaigns:
            return json.dumps(
                {
                    "error": (
                        f"No recruitment campaign exists for "
                        f"{slot.label or 'this event'} on "
                        f"{slot.date.isoformat()}."
                    )
                }
            )
        if len(campaigns) > 1:
            return json.dumps(
                {
                    "needs_clarification": True,
                    "matches": [
                        {
                            "campaign_id": str(c.id),
                            "status": c.status.value,
                            "created_at": c.created_at.isoformat()
                            if c.created_at else None,
                        }
                        for c in campaigns
                    ],
                    "message": (
                        f"Multiple campaigns exist for {slot.label or 'this event'} on "
                        f"{slot.date.isoformat()}. Reply with the campaign_id "
                        "of the one you want to delete."
                    ),
                }
            )
        target_campaign = campaigns[0]

    assert target_campaign is not None
    campaign = target_campaign

    # Resolve slot label/date for the confirmation message
    slot = await ctx.db.get(SpecificDateSlot, campaign.event_slot_id)
    label = (slot.label if slot and slot.label else "the event")
    date_str = slot.date.isoformat() if slot and slot.date else "?"

    # Step 1: Cancel PLANNED waves so the tick loop won't fire mid-delete
    if campaign.status in (
        CampaignStatus.DRAFT,
        CampaignStatus.AWAITING_APPROVAL,
        CampaignStatus.ACTIVE,
        CampaignStatus.PAUSED,
    ):
        cancel_res = await ctx.db.execute(
            RecruitmentWave.__table__.update()
            .where(
                RecruitmentWave.campaign_id == campaign.id,
                RecruitmentWave.status == WaveStatus.PLANNED,
            )
            .values(status=WaveStatus.CANCELLED)
        )
        cancelled_count = cancel_res.rowcount or 0
        await ctx.db.flush()
    else:
        cancelled_count = 0

    # Step 2: Detach announcements from this campaign's waves
    wave_ids_q = await ctx.db.execute(
        select(RecruitmentWave.id).where(
            RecruitmentWave.campaign_id == campaign.id
        )
    )
    wave_ids = list(wave_ids_q.scalars().all())
    if wave_ids:
        await ctx.db.execute(
            update(Announcement)
            .where(Announcement.recruitment_wave_id.in_(wave_ids))
            .values(recruitment_wave_id=None)
        )
        await ctx.db.flush()

    # Step 3: Delete campaign (cascades waves + signups + reports)
    prior_status = campaign.status.value
    campaign_id_str = str(campaign.id)
    await ctx.db.delete(campaign)
    await ctx.db.flush()
    # Commit so the deletion is visible even if downstream logic
    # raises later. Same belt-and-suspenders pattern as decision #5.
    try:
        await ctx.db.commit()
    except Exception:
        logger.exception(
            "Failed to commit campaign deletion %s", campaign_id_str
        )
        return json.dumps(
            {"error": "Could not delete campaign. Please try again."}
        )

    logger.info(
        "Deleted recruitment campaign %s (label=%s date=%s prior_status=%s cancelled_waves=%d total_waves=%d)",
        campaign_id_str, label, date_str, prior_status,
        cancelled_count, len(wave_ids),
    )

    cancel_note = (
        f" Cancelled {cancelled_count} pending wave{'s' if cancelled_count != 1 else ''}."
        if cancelled_count else ""
    )
    return json.dumps(
        {
            "ok": True,
            "campaign_id": campaign_id_str,
            "deleted_label": label,
            "deleted_date": date_str,
            "prior_status": prior_status,
            "cancelled_waves": cancelled_count,
            "total_waves_removed": len(wave_ids),
            "message": (
                f"Deleted the {label} campaign on {date_str} "
                f"(was {prior_status}).{cancel_note} Past SMS history is preserved."
            ),
        }
    )


async def handle_recruitment_status(
    ctx: ToolContext, tool_input: dict
) -> str:
    from app.agents.recruiter import executor

    if not ctx.is_admin:
        return json.dumps({"error": "Recruitment is an admin-only feature."})

    event_date_str = tool_input.get("event_date")
    event_date_filter: date | None = None
    if event_date_str:
        try:
            event_date_filter = date.fromisoformat(event_date_str)
        except ValueError:
            return json.dumps(
                {"error": "Invalid event_date format. Use YYYY-MM-DD."}
            )

    q = (
        select(RecruitmentCampaign, SpecificDateSlot)
        .join(
            SpecificDateSlot,
            SpecificDateSlot.id == RecruitmentCampaign.event_slot_id,
        )
        .where(
            RecruitmentCampaign.tenant_id == ctx.tenant.id,
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.ACTIVE,
                    CampaignStatus.PAUSED,
                ]
            ),
        )
        .order_by(SpecificDateSlot.date.asc())
    )
    if event_date_filter:
        q = q.where(SpecificDateSlot.date == event_date_filter)

    rows = (await ctx.db.execute(q)).all()
    if not rows:
        return json.dumps(
            {
                "message": (
                    "No active recruitment campaigns."
                    if not event_date_filter
                    else f"No active recruitment campaigns for {event_date_str}."
                )
            }
        )

    out: list[dict] = []
    for c, slot in rows:
        service_ids = [
            uuid.UUID(g["appointment_type_id"])
            for g in c.goals or []
            if g.get("appointment_type_id")
        ]
        signups = await executor.current_signups_per_service(
            ctx.db, slot, service_ids
        )
        targets = {
            g["appointment_type_id"]: int(g.get("target", 0))
            for g in c.goals or []
            if g.get("appointment_type_id")
        }
        out.append(
            {
                "campaign_id": str(c.id),
                "event_date": slot.date.isoformat(),
                "event_label": slot.label,
                "status": c.status.value,
                "fill": {
                    sid: {
                        "signups": int(signups.get(sid, 0)),
                        "target": targets.get(sid, 0),
                    }
                    for sid in targets
                },
            }
        )
    return json.dumps({"campaigns": out})
