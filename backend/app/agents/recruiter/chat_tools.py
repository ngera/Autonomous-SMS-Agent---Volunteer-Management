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
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import desc, select

from app.agents.recruiter import executor, planner
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
        # No pending campaign — let the LLM handle this naturally.
        return None

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
) -> str | None:
    """Server-side router for unambiguous status questions.

    The LLM has repeatedly fabricated campaign lists rather than calling
    ``recruitment_status``. Intercepting clean status queries here gives
    the admin a reliable answer based on real DB state.
    """
    if not _looks_like_status_query(message):
        return None

    from app.models.availability import SpecificDateSlot
    from app.models.appointment_type import AppointmentType
    from app.agents.recruiter.executor import current_signups_per_service

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
        return (
            "No recruitment campaigns are currently active or pending. "
            "Say 'plan recruitment for <event>' to start one."
        )

    # Service-name lookup
    type_ids = {
        uuid.UUID(g["appointment_type_id"])
        for c, _ in rows
        for g in (c.goals or [])
        if g.get("appointment_type_id")
    }
    type_names: dict[str, str] = {}
    if type_ids:
        nq = await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.id.in_(type_ids)
            )
        )
        type_names = {str(tid): name for tid, name in nq.all()}

    lines = [f"{len(rows)} campaign(s):"]
    for c, slot in rows:
        service_ids = [
            uuid.UUID(g["appointment_type_id"])
            for g in c.goals or []
            if g.get("appointment_type_id")
        ]
        signups = await current_signups_per_service(db, slot, service_ids)
        total_signed = sum(int(signups.get(sid, 0)) for sid in signups)
        total_min = sum(
            int(
                g.get("min_required")
                if g.get("min_required") is not None
                else g.get("target", 0)
                or 0
            )
            for g in c.goals or []
        )
        per_service = []
        for g in c.goals or []:
            sid = g.get("appointment_type_id")
            if not sid:
                continue
            name = type_names.get(sid, "service")
            sg = int(signups.get(sid, 0))
            mn = int(
                g.get("min_required")
                if g.get("min_required") is not None
                else g.get("target", 0)
                or 0
            )
            per_service.append(f"{name} {sg}/{mn}")
        per_service_str = (
            "; ".join(per_service) if per_service else "no services"
        )
        label = slot.label or "event"
        lines.append(
            f"- {label} ({slot.date.isoformat()}) "
            f"[{c.status.value}]: {total_signed}/{total_min} — {per_service_str}"
        )
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

    # 3. Upcoming events in next 60 days (id + label + date)
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
    events = list(ev_q.scalars().all())
    if events:
        ev_str = "; ".join(
            f"{s.label or 'event'} ({s.date.isoformat()})" for s in events
        )
    else:
        ev_str = "none"

    return (
        "=== CURRENT SYSTEM STATE — AUTHORITATIVE, OVERRIDES ANY "
        "CONFLICTING INFORMATION IN CONVERSATION HISTORY ===\n"
        f"- Today: {today.isoformat()}\n"
        f"{admin_line}\n"
        f"{phone_line}\n"
        f"- Active recruitment campaigns: {active_n}\n"
        f"- Campaigns awaiting your approval: {pending_n}\n"
        f"- Upcoming events (next 60 days): {ev_str}\n"
        "=== END CURRENT STATE ===\n"
        "If the conversation history says something that contradicts "
        "the above (e.g., \"your account has no SMS configured\" when "
        "the state above says CONFIGURED), the state above wins. Trust "
        "the current state, not the history.\n"
    )


async def handle_recruitment_status(
    ctx: ToolContext, tool_input: dict
) -> str:
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
