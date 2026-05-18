"""LLM-assisted planner for a recruitment campaign.

Runs as a one-shot tool-use loop (typically 3–6 Anthropic API calls per
campaign) that gathers facts about the event and proposes a policy +
message templates + a wave-by-wave preview. The terminal
``propose_plan`` tool persists the plan onto the campaign row and the
planner returns a short narrative for the SMS follow-up.

LLM seam #1 of the two-seam design (the other is ``reporter``).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.recruiter import targeting
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
)
from app.models.system_setting import SystemSetting
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsageSource
from app.modules.tool_executor import (
    DEFAULT_MODEL,
    run_tool_conversation,
)
from app.modules.tool_handlers import ToolContext
from app.services.token_usage import record_token_usage

logger = get_logger("recruiter.planner")


async def _get_ai_model(db: AsyncSession, tenant: Tenant | None) -> str:
    """Inline replacement for app.modules.conversation.get_ai_model.

    Duplicated here intentionally to avoid a planner → conversation →
    tool_executor → tool_handlers import cycle (tool_handlers transitively
    imports this module at the chat_tools registration point).
    """
    if not tenant:
        return DEFAULT_MODEL
    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key == "ai_model",
        )
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else DEFAULT_MODEL


# ── Planner tool definitions ──

PLANNER_TOOLS = [
    {
        "name": "get_event_details",
        "description": (
            "Get the event slot's date, time, location, services needed, "
            "and current signup counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_ranked_candidates",
        "description": (
            "Get the top-N currently-eligible volunteers for a service, "
            "ranked by experience score (positive scheduled/rescheduled/"
            "completed bookings on this and same-category services minus a "
            "no-show penalty over the lookback window). Use this to gauge "
            "how strong the candidate pool is before sizing waves."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_type_id": {
                    "type": "string",
                    "description": "Service UUID.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum candidates to return (default 20).",
                },
            },
            "required": ["appointment_type_id"],
        },
    },
    {
        "name": "get_recent_response_rates",
        "description": (
            "Estimate response rate for a service: of recently-messaged "
            "contacts for this service in the past N days, what fraction "
            "ended up booking? Use this to size waves with realistic "
            "overshoot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_type_id": {
                    "type": "string",
                    "description": "Service UUID.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Days to look back (default 60).",
                },
            },
            "required": ["appointment_type_id"],
        },
    },
    {
        "name": "propose_plan",
        "description": (
            "TERMINAL tool — call this exactly once when ready. Persists the "
            "recruitment plan onto the campaign and flips it to "
            "awaiting_approval. After this returns, emit a 1–2 sentence "
            "summary as the final assistant message (this becomes the SMS "
            "the admin receives)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy": {
                    "type": "object",
                    "description": (
                        "Policy fields. Recommended keys: wave_offsets_days "
                        "(list of int, days before event for each wave, "
                        "e.g. [14,7,3,1]), max_waves (int), overshoot_factor "
                        "(float, default 1.5), experience_lookback_days "
                        "(int, default 180), cooldown_hours_within_campaign "
                        "(int, default 48), per_wave_absolute_cap (int "
                        "optional)."
                    ),
                },
                "message_templates": {
                    "type": "object",
                    "description": (
                        "Map of wave_number (as string) → SMS template "
                        "string. Tokens supported: {first_name}, "
                        "{event_label}, {event_date}, {event_location}, "
                        "{service_name}. Provide either explicit per-wave "
                        "templates or a 'default' fallback."
                    ),
                },
                "plan_preview": {
                    "type": "object",
                    "description": (
                        "Concrete preview rendered for the admin: list of "
                        "wave entries with {wave_number, service_name, "
                        "scheduled_at_iso, target_count, rationale}."
                    ),
                },
            },
            "required": ["policy", "message_templates"],
        },
    },
]


# Canonical default lives in app/prompts/conversation.py (RECRUITMENT_AGENT_PROMPT)
# so it appears in the Admin Prompts editor and can be overridden per-tenant.
# Re-export here under the legacy name for backwards compatibility.
from app.prompts.conversation import (  # noqa: E402
    RECRUITMENT_AGENT_PROMPT as PLANNER_SYSTEM_PROMPT,
)


# ── Planner tool handlers ──


async def _h_get_event_details(ctx: ToolContext, _input: dict) -> str:
    """Return event slot + services + current signups."""
    pctx: PlannerContext = ctx  # type: ignore[assignment]
    slot = await pctx.db.get(SpecificDateSlot, pctx.event_slot_id)
    if not slot:
        return json.dumps({"error": "Event slot not found."})

    types_q = await pctx.db.execute(
        select(AppointmentType).where(
            AppointmentType.tenant_id == pctx.tenant.id
        )
    )
    types = {str(t.id): t for t in types_q.scalars().all()}

    services = []
    for entry in slot.service_config or []:
        type_id = entry.get("appointment_type_id")
        t = types.get(str(type_id)) if type_id else None
        # Current signups for this service on the event date
        count_q = await pctx.db.execute(
            select(func.count(Booking.id)).where(
                Booking.tenant_id == pctx.tenant.id,
                Booking.appointment_type_id == type_id,
                func.date(Booking.scheduled_at) == slot.date,
                Booking.status.in_(
                    [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
                ),
            )
        )
        current = int(count_q.scalar() or 0)
        services.append(
            {
                "appointment_type_id": str(type_id) if type_id else None,
                "service_name": t.name if t else None,
                "category": t.category if t else None,
                "min_required": entry.get("min_required", 1),
                "max_allowed": entry.get("max_allowed"),
                "current_signups": current,
            }
        )

    return json.dumps(
        {
            "event_slot_id": str(slot.id),
            "event_date": slot.date.isoformat(),
            "event_start_time": slot.start_time.strftime("%H:%M")
            if slot.start_time
            else None,
            "event_end_time": slot.end_time.strftime("%H:%M")
            if slot.end_time
            else None,
            "label": slot.label,
            "location": slot.location,
            "description": slot.description,
            "services": services,
        }
    )


async def _h_get_ranked_candidates(ctx: ToolContext, tool_input: dict) -> str:
    pctx: PlannerContext = ctx  # type: ignore[assignment]
    type_id_str = tool_input.get("appointment_type_id")
    if not type_id_str:
        return json.dumps({"error": "appointment_type_id is required."})
    try:
        service_id = uuid.UUID(type_id_str)
    except (ValueError, TypeError):
        return json.dumps({"error": "Invalid appointment_type_id."})
    limit = int(tool_input.get("limit", 20))

    slot = await pctx.db.get(SpecificDateSlot, pctx.event_slot_id)
    campaign = await pctx.db.get(RecruitmentCampaign, pctx.campaign_id)
    if not slot or not campaign:
        return json.dumps({"error": "Event slot or campaign missing."})

    result = await targeting.select_recipients(
        pctx.db, campaign, slot, service_id, wave_number=1
    )
    # Trim to limit for the planner; full pool size is also useful info
    top = result.contacts[:limit]
    return json.dumps(
        {
            "eligible_pool_size": result.eligible_pool_size,
            "returned": len(top),
            "candidates": [
                {
                    "contact_id": str(c.contact_id),
                    "name": c.name,
                    "score": c.score,
                    "this_service_count": c.this_service_count,
                    "same_category_count": c.same_category_count,
                    "no_show_count": c.no_show_count,
                }
                for c in top
            ],
            "selection_reason": result.selection_reason,
        }
    )


async def _h_get_recent_response_rates(
    ctx: ToolContext, tool_input: dict
) -> str:
    """Cheap response-rate estimate.

    For the given service, look at announcements with that service in
    filter_appointment_type_ids over the lookback window and compute
    (recipients who booked the same service after the announcement) /
    (total recipients across those announcements). Approximate — we don't
    track per-recipient delivery in announcements — but useful directional
    info for the planner.
    """
    from app.models.announcement import Announcement

    pctx: PlannerContext = ctx  # type: ignore[assignment]
    type_id_str = tool_input.get("appointment_type_id")
    try:
        service_id = uuid.UUID(type_id_str) if type_id_str else None
    except (ValueError, TypeError):
        return json.dumps({"error": "Invalid appointment_type_id."})
    if not service_id:
        return json.dumps({"error": "appointment_type_id is required."})

    lookback_days = int(tool_input.get("lookback_days", 60))
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    ann_q = await pctx.db.execute(
        select(
            func.coalesce(func.sum(Announcement.sent_count), 0),
        ).where(
            Announcement.tenant_id == pctx.tenant.id,
            Announcement.sent_at >= cutoff,
            Announcement.filter_appointment_type_ids.is_not(None),
        )
    )
    total_messaged = int(ann_q.scalar() or 0)

    bookings_q = await pctx.db.execute(
        select(func.count(Booking.id)).where(
            Booking.tenant_id == pctx.tenant.id,
            Booking.appointment_type_id == service_id,
            Booking.created_at >= cutoff,
            Booking.status.in_(
                [
                    BookingStatus.SCHEDULED,
                    BookingStatus.RESCHEDULED,
                    BookingStatus.COMPLETED,
                ]
            ),
        )
    )
    bookings = int(bookings_q.scalar() or 0)

    rate = bookings / total_messaged if total_messaged else None
    return json.dumps(
        {
            "lookback_days": lookback_days,
            "total_messaged_estimate": total_messaged,
            "bookings_for_service": bookings,
            "approx_response_rate": rate,
            "note": (
                "Approximate; not per-recipient. Treat as a directional "
                "signal for overshoot sizing."
            ),
        }
    )


async def _h_propose_plan(ctx: ToolContext, tool_input: dict) -> str:
    """Terminal: persist plan onto the campaign + flip to awaiting_approval."""
    pctx: PlannerContext = ctx  # type: ignore[assignment]
    campaign = await pctx.db.get(RecruitmentCampaign, pctx.campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found."})

    policy = tool_input.get("policy") or {}
    templates = tool_input.get("message_templates") or {}
    preview = tool_input.get("plan_preview") or {}

    # Sanity floor on policy values — guard against bad LLM output.
    if "overshoot_factor" in policy:
        try:
            of = float(policy["overshoot_factor"])
            policy["overshoot_factor"] = max(1.0, min(of, 3.0))
        except (ValueError, TypeError):
            policy.pop("overshoot_factor", None)

    campaign.policy = policy
    campaign.message_templates = templates
    campaign.plan_preview = preview
    campaign.status = CampaignStatus.AWAITING_APPROVAL
    await pctx.db.flush()
    pctx.terminal_called = True
    logger.info("Planner proposed plan for campaign %s", campaign.id)
    return json.dumps(
        {
            "ok": True,
            "campaign_id": str(campaign.id),
            "status": campaign.status.value,
        }
    )


PLANNER_HANDLERS = {
    "get_event_details": _h_get_event_details,
    "get_ranked_candidates": _h_get_ranked_candidates,
    "get_recent_response_rates": _h_get_recent_response_rates,
    "propose_plan": _h_propose_plan,
}


# ── Planner context (shim over ToolContext so handlers stay simple) ──


class PlannerContext(ToolContext):
    """Extends ToolContext with campaign + event slot ids for planner tools.

    The shared tool_use loop expects a ``ToolContext`` shape; we subclass
    rather than fork the loop. The unused contact_phone / contact_id /
    is_admin fields are populated with placeholders.
    """

    def __init__(
        self,
        db,
        tenant: Tenant,
        campaign_id: uuid.UUID,
        event_slot_id: uuid.UUID,
    ):
        super().__init__(
            db=db,
            tenant=tenant,
            contact_phone="",
            contact_id=uuid.UUID(int=0),
            is_admin=True,
            test_mode=False,
        )
        self.campaign_id = campaign_id
        self.event_slot_id = event_slot_id
        self.terminal_called: bool = False


# ── Entrypoint ──


async def run_planner(campaign_id: uuid.UUID) -> str | None:
    """Run the planner loop end-to-end for one campaign.

    Opens its own DB session. Returns the LLM's final narrative summary
    (used as the SMS body) or ``None`` on failure.
    """
    import asyncio as _asyncio
    async with async_session_factory() as db:
        # Defensive: the originating request commits the campaign row
        # before scheduling us, but in the rare case our task starts in the
        # same tick before the commit lands, retry a few times instead of
        # silently aborting with "not found".
        campaign = None
        for attempt in range(5):
            campaign = await db.get(RecruitmentCampaign, campaign_id)
            if campaign:
                break
            await _asyncio.sleep(0.2)
        if not campaign:
            logger.error(
                "Planner: campaign %s not found after retries — aborting",
                campaign_id,
            )
            return None
        tenant = await db.get(Tenant, campaign.tenant_id)
        if not tenant:
            logger.error(
                "Planner: tenant for campaign %s not found", campaign_id
            )
            return None

        ctx = PlannerContext(
            db=db,
            tenant=tenant,
            campaign_id=campaign.id,
            event_slot_id=campaign.event_slot_id,
        )

        model = await _get_ai_model(db, tenant)
        api_key = tenant.anthropic_api_key or settings.anthropic_api_key

        system_prompt = await _resolve_system_prompt(db, tenant.id)

        # Seed user message — the LLM uses tools to discover details.
        user_message = (
            f"Plan recruitment for campaign {campaign.id}. "
            f"Begin by calling get_event_details."
        )

        # Rate-limit guard (see design_decisions.md #15). The planner is a
        # multi-round tool-use loop; we count it as 1 call against the
        # tenant budget to keep accounting simple.
        from app.services.llm_rate_limit import (
            consume,
            get_tenant_limit,
            LLMRateLimitExceeded,
        )
        try:
            tenant_limit = await get_tenant_limit(db, tenant.id)
            await consume(tenant.id, limit=tenant_limit)
        except LLMRateLimitExceeded:
            logger.warning(
                "Planner aborted for campaign %s — tenant rate limit",
                campaign.id,
            )
            campaign.status = CampaignStatus.FAILED
            await db.commit()
            return None

        try:
            result = await run_tool_conversation(
                system_prompt=system_prompt,
                tools=PLANNER_TOOLS,
                messages=[{"role": "user", "content": user_message}],
                ctx=ctx,
                api_key=api_key,
                model=model,
                max_rounds=8,
                handlers=PLANNER_HANDLERS,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Planner conversation failed: %s", e)
            campaign.status = CampaignStatus.FAILED
            await db.commit()
            return None

        # Record token usage
        try:
            await record_token_usage(
                db=db,
                tenant_id=tenant.id,
                source=TokenUsageSource.CONVERSATION,
                model=result.model,
                input_tokens=result.total_input_tokens,
                output_tokens=result.total_output_tokens,
                contact_id=None,
                contact_phone=None,
                tool_calls=ctx.tool_calls if ctx.tool_calls else None,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to record planner token usage")

        # Persist plan_summary (the LLM's final narrative). If the planner
        # didn't reach propose_plan, fall back to a deterministic default
        # plan derived from the event slot — better than marking the
        # campaign failed and leaving the admin stuck.
        await db.refresh(campaign)
        if not ctx.terminal_called:
            logger.warning(
                "Planner did not call propose_plan for campaign %s — "
                "falling back to deterministic default plan",
                campaign.id,
            )
            try:
                summary = await _apply_default_plan(db, campaign, tenant)
                campaign.plan_summary = summary
                await db.commit()
                return summary
            except Exception:
                logger.exception(
                    "Default plan fallback failed for campaign %s",
                    campaign.id,
                )
                campaign.status = CampaignStatus.FAILED
                await db.commit()
                return None

        campaign.plan_summary = result.text
        await db.commit()
        return result.text


async def _apply_default_plan(
    db: AsyncSession,
    campaign: RecruitmentCampaign,
    tenant: Tenant,
) -> str:
    """Generate a sensible default plan from the event slot's service_config.

    Used when the LLM planner stalls without calling propose_plan. Mirrors
    what the LLM would propose: standard wave offsets, default policy
    values, simple per-wave message templates, and a wave preview computed
    from the event date.
    """
    from datetime import date as _date, datetime as _dt, timedelta
    from app.models.availability import SpecificDateSlot
    from app.models.appointment_type import AppointmentType

    slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
    if not slot:
        raise RuntimeError("event slot disappeared")

    type_ids = [
        uuid.UUID(g["appointment_type_id"])
        for g in campaign.goals or []
        if g.get("appointment_type_id")
    ]
    types_q = await db.execute(
        select(AppointmentType).where(AppointmentType.id.in_(type_ids))
    )
    type_name_by_id = {str(t.id): t.name for t in types_q.scalars().all()}

    today = _date.today()
    days_to_event = max(0, (slot.date - today).days)
    # Use as many of [14, 7, 3, 1] as fit before the event; if very close,
    # fire one wave immediately at offset 0.
    candidate_offsets = [14, 7, 3, 1]
    offsets = [d for d in candidate_offsets if d <= days_to_event]
    if not offsets:
        offsets = [0]

    policy = {
        "wave_offsets_days": offsets,
        "overshoot_factor": 1.5,
        "experience_lookback_days": 180,
        "cooldown_hours_within_campaign": 48,
        "max_waves": len(offsets),
    }

    from app.prompts.conversation import get_recruitment_message_template
    message_templates = {
        "default": await get_recruitment_message_template(db, tenant.id),
    }

    # Wave preview: per (service, offset) one entry, scheduled_at = event - offset days
    event_dt = _dt.combine(slot.date, slot.start_time or _dt.min.time())
    waves_preview: list[dict] = []
    for goal in campaign.goals or []:
        sid = goal.get("appointment_type_id")
        if not sid:
            continue
        target = goal.get("min_required") or goal.get("target") or 1
        for idx, off in enumerate(sorted(offsets, reverse=True), start=1):
            scheduled_at = event_dt - timedelta(days=off)
            waves_preview.append(
                {
                    "wave_number": idx,
                    "service_name": type_name_by_id.get(sid, "service"),
                    "scheduled_at_iso": scheduled_at.isoformat(),
                    "target_count": target,
                    "rationale": (
                        f"T-{off}d wave for {type_name_by_id.get(sid, 'service')}"
                    ),
                }
            )

    plan_preview = {"waves": waves_preview}

    campaign.policy = policy
    campaign.message_templates = message_templates
    campaign.plan_preview = plan_preview
    campaign.status = CampaignStatus.AWAITING_APPROVAL

    total_needed = sum(
        int(g.get("min_required") or g.get("target") or 0)
        for g in campaign.goals or []
    )
    first_wave = (
        sorted(waves_preview, key=lambda w: w["scheduled_at_iso"])[0]
        if waves_preview else None
    )
    when = (
        first_wave["scheduled_at_iso"][:10]
        if first_wave else "today"
    )
    summary = (
        f"Default plan for {slot.label or 'event'} on {slot.date.isoformat()}: "
        f"{total_needed} volunteers needed across "
        f"{len(campaign.goals or [])} service(s); first wave {when}. "
        f"Edit in dashboard or reply APPROVE to start."
    )
    if len(summary) > 380:
        summary = summary[:377] + "..."
    return summary


async def _resolve_system_prompt(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Look up the per-tenant override for the recruitment agent prompt.

    Uses the same key (``prompt_recruitment_agent``) that the Admin Prompts
    editor saves under, so changes in the UI flow through here on the next
    planner run.
    """
    override_q = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == "prompt_recruitment_agent",
        )
    )
    override = override_q.scalar_one_or_none()
    if override and override.value:
        return override.value
    return PLANNER_SYSTEM_PROMPT


__all__ = ["run_planner", "PLANNER_TOOLS", "PLANNER_HANDLERS"]
