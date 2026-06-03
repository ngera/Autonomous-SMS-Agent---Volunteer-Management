"""Hybrid intent dispatcher — Tier 2 glue for volunteer engagement.

Sits between the regex routers in ``app.agents.engagement.intents`` (Tier 1)
and the full customer LLM (Tier 3). Caller invokes this AFTER Tier 1
returned ``None`` and BEFORE handing the message to the LLM.

Flow:
  1. Call ``intent_classifier.classify`` on the message.
  2. If the classifier returns "other" / low confidence / API failure,
     return ``None`` and let the caller fall through to the LLM.
  3. Otherwise synthesize a canonical phrase the regex routers already
     understand, then re-invoke the matching ``maybe_handle_*``.
     This reuses every guardrail in the regex routers (live-booking
     resolution, pending_intent flow, prompt templates, audit writes)
     so we don't fork the safety net.

The canonical phrases are intentionally minimal — just enough to satisfy
the Tier 1 regex — so the second pass behaves identically to a volunteer
who typed the canonical form to begin with.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.engagement import intent_classifier
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.tenant import Tenant

logger = get_logger("engagement.intent_dispatch")


async def maybe_handle_via_classifier(
    db: AsyncSession,
    *,
    tenant: Tenant,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
) -> str | None:
    """Tier 2 entrypoint. Returns a reply string when the classifier
    confidently identifies an engagement intent and we can act on it.
    Returns ``None`` to fall through to the full LLM.
    """
    if not message_body or not message_body.strip():
        return None

    decision = await intent_classifier.classify(message_body, db, tenant)
    if decision is None:
        return None

    if decision.intent == "other":
        return None

    if decision.confidence < intent_classifier.CONFIDENCE_THRESHOLD:
        logger.info(
            "Engagement classifier below threshold (%.2f < %.2f) — fall through",
            decision.confidence,
            intent_classifier.CONFIDENCE_THRESHOLD,
        )
        return None

    # SWITCH / ALSO need a service reference to act. Without one the
    # regex router can't extract a service name and would no-op silently.
    if decision.intent in {"switch", "also"} and not decision.service_reference:
        logger.info(
            "Engagement classifier picked %s but service_reference is empty — fall through",
            decision.intent,
        )
        return None

    # Lazy import — engagement.intents imports services that pull in
    # the wider model graph; deferring avoids cycles at module load.
    from app.agents.engagement.intents import (
        maybe_handle_check_out,
        maybe_handle_here_check_in,
        maybe_handle_reentry,
        maybe_handle_service_add,
        maybe_handle_service_switch,
    )

    intent = decision.intent

    if intent == "here":
        # Synthesize the canonical HERE; the regex router resolves the
        # actual booking and handles multi-event disambiguation,
        # already-checked-in idempotency, and re-entry detection
        # (so misclassified "reentry" as "here" still does the right thing).
        return await maybe_handle_here_check_in(
            db,
            contact=contact,
            conversation=conversation,
            message_body="HERE",
        )

    if intent == "reentry":
        # Reentry depends on a pending checkout_reentry_confirmation
        # being set. If the volunteer has already checked out and the
        # confirmation prompt was sent, BACK lands them; otherwise the
        # regex router returns None and we fall through to "here".
        reply = await maybe_handle_reentry(
            db,
            contact=contact,
            conversation=conversation,
            message_body="BACK",
        )
        if reply is not None:
            return reply
        return await maybe_handle_here_check_in(
            db,
            contact=contact,
            conversation=conversation,
            message_body="HERE",
        )

    if intent == "done":
        return await maybe_handle_check_out(
            db,
            contact=contact,
            conversation=conversation,
            message_body="DONE",
        )

    if intent == "switch":
        synthetic = f"switch to {decision.service_reference}"
        return await maybe_handle_service_switch(
            db,
            contact=contact,
            conversation=conversation,
            message_body=synthetic,
        )

    if intent == "also":
        synthetic = f"also {decision.service_reference}"
        return await maybe_handle_service_add(
            db,
            contact=contact,
            conversation=conversation,
            message_body=synthetic,
        )

    logger.warning(
        "Engagement classifier returned actionable intent %r but dispatcher "
        "has no handler — falling through to LLM",
        intent,
    )
    return None
