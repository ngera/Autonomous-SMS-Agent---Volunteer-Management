"""Hybrid intent-detection dispatcher — Tier 2 glue.

Sits between the regex routers (Tier 1, in ``app.agents.recruiter.chat_tools``)
and the full admin LLM (Tier 3). Caller invokes this AFTER Tier 1
returned ``None`` (no regex hit) and BEFORE handing the message to the
LLM.

Flow:
  1. Call ``intent_classifier.classify`` on the message.
  2. If the classifier returns "other" / low confidence / API failure
     → return ``None`` and let the caller fall through to the full LLM.
  3. Otherwise synthesize a canonical phrase the regex routers already
     understand, then re-invoke the matching ``maybe_handle_*_directly``.
     This reuses all the date parsing, label normalization, and
     disambiguation logic so we don't fork the safety net.
  4. For destructive intents (``delete_campaign``) — surface a
     confirmation prompt rather than acting, even at high confidence.

See ``memory/design_decisions.md`` #22 for the why.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import intent_classifier
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.modules.tool_handlers import ToolContext

logger = get_logger("orchestrator.intent_dispatch")


async def maybe_handle_via_classifier(
    db: AsyncSession,
    tenant: Tenant,
    message: str,
    admin_user: AdminUser | None,
    ctx: ToolContext,
) -> str | None:
    """Tier 2 entrypoint. Returns a reply string when the classifier
    confidently identifies a recruitment intent and we can act on it.
    Returns ``None`` to fall through to the full LLM.
    """
    if not message or not message.strip():
        return None

    decision = await intent_classifier.classify(message, db, tenant)
    if decision is None:
        return None

    if decision.intent == "other":
        # Classifier explicitly said "not a recruitment action". Even at
        # very high confidence we hand to the LLM — that's its job.
        return None

    # Below-threshold confidence on any action intent: ask rather than
    # act. False positives on action intents are worse than false
    # negatives (admin can rephrase; we can't unsend an outreach wave).
    if decision.confidence < intent_classifier.CONFIDENCE_THRESHOLD:
        return _build_low_confidence_prompt(decision)

    # Destructive intents: always confirm, even at high confidence.
    # See _DESTRUCTIVE_INTENTS in intent_classifier — delete cascades
    # through waves + announcements and is not idempotent.
    if decision.requires_confirmation:
        return _build_destructive_confirmation_prompt(decision)

    # Lazy import — chat_tools depends on tool_handlers which depends on
    # things this module also touches. Defer to break the cycle.
    from app.agents.recruiter.chat_tools import (
        maybe_handle_approval_directly,
        maybe_handle_list_events_directly,
        maybe_handle_start_campaign_directly,
        maybe_handle_status_directly,
    )

    intent = decision.intent
    event_ref = (decision.event_reference or "").strip()

    if intent == "approve":
        # The regex router's APPROVAL_PHRASES set requires an exact
        # match. Synthesize "approve" so it dispatches reliably.
        return await maybe_handle_approval_directly(
            db, tenant, "approve", admin_user
        )

    if intent == "list_events":
        return await maybe_handle_list_events_directly(
            ctx, "list upcoming events"
        )

    if intent == "status":
        # The status router filters by event label/date when present —
        # discarding the classifier's event_reference here was making
        # "what is the status of awareness seminar" render every active
        # campaign instead of just that one. Pass the ref through so
        # _extract_status_filter can narrow the result.
        if event_ref:
            synthetic = f"status of {event_ref} campaign"
        else:
            synthetic = "list active campaigns"
        return await maybe_handle_status_directly(
            db, tenant, synthetic, admin_id=admin_user.id
        )

    if intent == "start_planning":
        if event_ref:
            synthetic = f"plan recruitment for {event_ref}"
        else:
            # No event reference → hit the bare-intent path so the router
            # auto-targets the unique upcoming event or asks which one.
            synthetic = "start planning"
        logger.info(
            "Classifier → start_planning, dispatching via regex router "
            "(synthetic=%r)",
            synthetic,
        )
        return await maybe_handle_start_campaign_directly(ctx, synthetic)

    if intent == "cancel_muster":
        return await _dispatch_cancel_muster(db, tenant, event_ref)

    if intent == "restart_muster":
        return await _dispatch_restart_muster(db, tenant, event_ref)

    # Unknown intent that survived validation (shouldn't happen given
    # _VALID_INTENTS gating in the classifier, but be defensive).
    logger.warning(
        "Classifier returned actionable intent %r but dispatcher has no "
        "handler — falling through to LLM",
        intent,
    )
    return None


def _build_low_confidence_prompt(
    decision: intent_classifier.IntentDecision,
) -> str:
    """Ask the admin to confirm an uncertain classification rather than
    acting. Phrases each intent in the admin's natural verb so the
    confirmation reply is unambiguous."""
    intent_phrasing = {
        "start_planning": "start a muster",
        "approve": "approve the pending muster plan",
        "delete_muster": "delete a muster",
        "cancel_muster": "cancel a muster",
        "restart_muster": "restart a cancelled muster",
        "list_events": "see your upcoming events",
        "status": "see active musters",
    }
    action = intent_phrasing.get(decision.intent, "do that")
    event_part = (
        f" for {decision.event_reference}"
        if decision.event_reference
        and decision.intent
        in {
            "start_planning",
            "delete_muster",
            "cancel_muster",
            "restart_muster",
        }
        else ""
    )
    return (
        f"Did you mean to {action}{event_part}? "
        f"Reply 'yes' to confirm, or rephrase what you'd like me to do."
    )


def _build_destructive_confirmation_prompt(
    decision: intent_classifier.IntentDecision,
) -> str:
    """Destructive intents always confirm. The admin must explicitly
    type the canonical phrase to actually trigger the delete — that
    phrase matches the Tier 1 regex router so the second turn dispatches
    cleanly without going through the classifier again.
    """
    if decision.intent == "delete_muster":
        if decision.event_reference:
            return (
                f"You want to delete the muster for "
                f"{decision.event_reference}? This cancels any pending "
                f"outreach waves and removes the muster permanently.\n\n"
                f"To confirm, reply: "
                f"'delete the muster for {decision.event_reference}'"
            )
        return (
            "You want to delete a muster? This cancels any pending "
            "outreach waves and removes the muster permanently.\n\n"
            "To confirm, reply: 'delete this muster' "
            "(if there's only one active) — or tell me which event the "
            "muster is for."
        )
    # Future destructive intents land here.
    return (
        "That looks like a destructive action. Could you tell me explicitly "
        "what you want to delete or cancel?"
    )


async def _resolve_active_muster(
    db, tenant, event_ref: str, *, include_terminal: bool = False
):
    """Resolve the campaign + slot the admin's event reference points at.

    Returns (campaign, slot, error_string). When error_string is set,
    the caller should send it back as the SMS reply verbatim — it's
    either "no match" or "multiple, please disambiguate".
    """
    from sqlalchemy import select
    from app.agents.recruiter.chat_tools import (
        _extract_status_filter,
        _filter_campaigns_by_event,
    )
    from app.models.availability import SpecificDateSlot
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentCampaign,
    )

    if include_terminal:
        status_set = [
            CampaignStatus.CANCELLED,
            CampaignStatus.FAILED,
        ]
    else:
        status_set = [
            CampaignStatus.DRAFT,
            CampaignStatus.AWAITING_APPROVAL,
            CampaignStatus.ACTIVE,
            CampaignStatus.PAUSED,
        ]

    rows = list((await db.execute(
        select(RecruitmentCampaign, SpecificDateSlot)
        .join(
            SpecificDateSlot,
            SpecificDateSlot.id == RecruitmentCampaign.event_slot_id,
        )
        .where(
            RecruitmentCampaign.tenant_id == tenant.id,
            RecruitmentCampaign.status.in_(status_set),
        )
    )).all())
    if not rows:
        return (
            None,
            None,
            (
                "No cancelled or failed muster found to restart."
                if include_terminal
                else "No active muster found to cancel."
            ),
        )

    filter_date, filter_label = _extract_status_filter(event_ref or "")
    if filter_date or filter_label:
        filtered = _filter_campaigns_by_event(rows, filter_date, filter_label)
        if filtered:
            rows = filtered

    if len(rows) > 1:
        lines = []
        for c, s in rows[:5]:
            lines.append(
                f"  • {s.label or 'event'} on "
                f"{s.date.isoformat() if s.date else '?'} "
                f"({c.status.value})"
            )
        return (
            None,
            None,
            "Multiple match. Which one?\n"
            + "\n".join(lines)
            + "\nReply with the date (YYYY-MM-DD) or the event name.",
        )

    c, s = rows[0]
    return (c, s, None)


async def _dispatch_cancel_muster(db, tenant, event_ref: str) -> str:
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentWave,
        WaveStatus,
    )
    from sqlalchemy import update as _sa_update

    campaign, slot, err = await _resolve_active_muster(
        db, tenant, event_ref, include_terminal=False
    )
    if err:
        return err

    campaign.status = CampaignStatus.CANCELLED
    await db.execute(
        _sa_update(RecruitmentWave)
        .where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.PLANNED,
        )
        .values(status=WaveStatus.CANCELLED)
    )
    await db.flush()
    return (
        f"Cancelled muster for {slot.label or 'event'} on "
        f"{slot.date.isoformat()}. No further SMS will go out. "
        f"Reply 'restart muster for {slot.label or 'event'}' to bring it back."
    )


async def _dispatch_restart_muster(db, tenant, event_ref: str) -> str:
    from datetime import datetime, timezone
    from app.models.recruitment_campaign import (
        CampaignStatus,
        RecruitmentWave,
        WaveStatus,
    )
    from sqlalchemy import select

    campaign, slot, err = await _resolve_active_muster(
        db, tenant, event_ref, include_terminal=True
    )
    if err:
        return err

    if slot.date < datetime.now(timezone.utc).date():
        return (
            f"Event for {slot.label or 'event'} on "
            f"{slot.date.isoformat()} has already passed; create a new "
            "muster instead."
        )

    campaign.status = CampaignStatus.ACTIVE
    now = datetime.now(timezone.utc)
    revived = (await db.execute(
        select(RecruitmentWave).where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.CANCELLED,
            RecruitmentWave.scheduled_at > now,
        )
    )).scalars().all()
    for w in revived:
        w.status = WaveStatus.PLANNED
    await db.flush()
    n = len(revived)
    return (
        f"Restarted muster for {slot.label or 'event'} on "
        f"{slot.date.isoformat()}. "
        + (
            f"{n} future wave{'s' if n != 1 else ''} re-queued."
            if n
            else "No future waves to re-queue — you may need to re-plan."
        )
    )
