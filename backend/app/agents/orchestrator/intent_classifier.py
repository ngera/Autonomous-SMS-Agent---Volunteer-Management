"""Haiku-based intent classifier — Tier 2 of the hybrid intent
detection stack for admin SMS.

Pipeline (see ``memory/design_decisions.md`` #22):

  Tier 1  Deterministic regex routers in
          ``app.agents.recruiter.chat_tools.maybe_handle_*_directly``.
          Free + instant. Covers the ~80% of common phrasings.

  Tier 2  THIS MODULE. Haiku JSON-mode classifier. Covers the long
          tail of novel phrasings that regex misses. ~200-500ms +
          ~$0.0001/call. Fires only when Tier 1 returns None.

  Tier 3  Full admin LLM with tools. Multi-turn chat, explanations,
          questions, anything that's not a recruitment action.

The classifier returns a structured ``IntentDecision`` the caller can
use to dispatch into the same handlers Tier 1 would have invoked —
reusing the regex routers' date parsing, label cleaning, and
disambiguation logic so the safety net stays consistent.

Guardrails:
  - Confidence threshold (``CONFIDENCE_THRESHOLD``) — below it we ask
    the admin to confirm rather than acting silently.
  - Destructive intents (``_DESTRUCTIVE_INTENTS``) — always require
    explicit re-confirmation even at high confidence. The cost of a
    false-positive delete (cascading cancel of waves + announcements)
    is much higher than one extra admin tap.
  - Soft-fail on API error — return ``None`` and let the full LLM
    handle it. Don't block the admin on a Haiku outage.

See also ``app.agents.orchestrator.crisis`` — the other classifier seam
under the Orchestrator umbrella, same pattern.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.tenant import Tenant

logger = get_logger("orchestrator.intent_classifier")


# ── Tunables ──
# 0.7 chosen empirically as the floor for "act without re-asking". Below
# this we surface a confirmation prompt; above this we dispatch (unless
# the intent is destructive — see _DESTRUCTIVE_INTENTS).
CONFIDENCE_THRESHOLD = 0.7

# Haiku is fast; cap latency so a slow API call can't add seconds to the
# admin's response time. 4s leaves room for one retry inside httpx but
# is well below the conversational threshold where the admin assumes
# something broke.
_HTTP_TIMEOUT_SECONDS = 4.0

_VALID_INTENTS = frozenset(
    {
        "start_planning",
        "approve",
        # Muster-specific intents (event staffing from the existing
        # volunteer pool). Renamed from the generic *_campaign forms
        # so when Fundraising Campaigns + Recruiting Campaigns ship,
        # admins can address each type unambiguously.
        "delete_muster",
        "cancel_muster",
        "restart_muster",
        "list_events",
        "status",
        "other",
    }
)

# Intents we never auto-dispatch — always surface a confirmation prompt
# even at high confidence. Today: delete (irreversible row removal +
# cascading wave cleanup). Cancel and restart are reversible (admin can
# undo each via the other) so they don't need the extra friction.
_DESTRUCTIVE_INTENTS = frozenset({"delete_muster"})


_SYSTEM_PROMPT = """You are an intent classifier for admin SMS messages \
to a volunteer-recruitment system. Classify the user's last message \
into exactly one intent and return STRICT JSON.

CAMPAIGN-TYPE VOCABULARY:
The product has three distinct campaign types. Only ONE is wired today (Musters).
Future-proof your classification:
  - MUSTER — fills an existing event from the existing volunteer pool. The
    delete/cancel/restart intents below are MUSTER-SPECIFIC. Synonyms:
    "muster", "campaign" used alongside event references like "for the gala",
    "staffing for X", "recruit for X event", "fill X".
  - FUNDRAISING CAMPAIGN — donor outreach. Synonyms: "fundraiser", "appeal",
    "donation campaign", "marketing campaign", "donor outreach". NOT YET
    BUILT — never classify a fundraising-flavored ask as muster.
  - RECRUITING CAMPAIGN — bringing NEW volunteers into the pool (no event
    yet). Synonyms: "recruiting campaign", "hiring campaign", "find new
    volunteers", "volunteer drive". NOT YET BUILT — never classify a
    pool-growth ask as muster.

When the admin says bare "campaign" with no event reference AND no other
clue about type → classify as "other" so we ask for clarification rather
than mis-routing through a muster handler.

Valid intents:
- "start_planning"   admin wants to start a MUSTER for an event
- "approve"          admin is approving a muster plan that's awaiting approval
- "delete_muster"    admin wants to permanently DELETE/REMOVE a MUSTER from the database
- "cancel_muster"    admin wants to STOP/CANCEL a MUSTER (keeps the row, halts further waves)
- "restart_muster"   admin wants to RESTART/REVIVE a previously cancelled or failed MUSTER
- "list_events"      admin is asking what upcoming events exist
- "status"           admin is asking what musters are active/running
- "other"            anything else (greetings, questions, off-topic, ambiguous campaign type)

Rules:
1. Output JSON only. No prose, no markdown fence. Schema:
   {"intent": "<one of above>", "confidence": <0.0..1.0>, "event_reference": "<phrase or null>", "reasoning": "<one short sentence>"}
2. "event_reference" is the noun phrase identifying the event (e.g. "food drive on June 15", "the gala", "annual prize distribution"). Use null when the admin's message has no event reference.
3. "confidence" is your honest self-assessed probability that this classification matches the admin's true intent. Be calibrated — use < 0.7 when the message is ambiguous or could plausibly mean something else.
4. Prefer "other" when uncertain. False positives on action intents are worse than false negatives.
5. "approve" should NEVER include verbs like "plan", "start", "begin", "delete", "cancel", "restart" — those are different intents.
6. "delete_muster" is the IRREVERSIBLE remove-from-database action FOR A MUSTER. Match strong wording like "delete the muster for X" / "scrap the muster" / "wipe the X muster". Does NOT match the word "cancel" (use "cancel_muster"). REQUIRES a muster identifier — either an event reference OR an explicit "muster" / "staffing campaign" hint. Bare "delete the campaign" with no muster clue → "other".
7. "cancel_muster" matches "cancel", "stop", "halt", "hold off on", "call off" applied SPECIFICALLY to a muster / event-staffing campaign. Distinguished from delete: cancel just stops sending; delete removes the row. Bare "cancel the campaign" with no muster clue (e.g. the admin might mean a future fundraising campaign) → "other".
8. "restart_muster" matches "restart", "resume", "revive", "bring back", "start again", "re-enable", "un-cancel" applied SPECIFICALLY to an existing cancelled/failed muster. NOT a fresh "start_planning". Bare "restart the campaign" with no muster clue → "other".
9. "list_events" is about UPCOMING EVENTS on the schedule. "status"/"list campaigns" is about ACTIVE MUSTERS. They are different — read carefully.
10. Approve phrases: "ok", "yes", "go", "approved", "approve it", "do it", "looks good", "lgtm", "ship it", "proceed". Only classify as "approve" if the message is short and unambiguous; long messages with "yes" embedded should be "other".
11. Fundraising / marketing / donor / recruiting-new-volunteers wording → always "other" (those backends aren't wired; the LLM will explain that)."""


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    event_reference: str | None
    reasoning: str | None
    requires_confirmation: bool
    raw_text: str | None
    latency_ms: int


async def classify(
    message: str,
    db: AsyncSession,
    tenant: Tenant,
) -> IntentDecision | None:
    """Classify an admin message via Haiku.

    Returns ``None`` when the API call fails, the response is
    unparseable, or the message is empty — caller should fall through
    to the full LLM in any of those cases. Soft-fail by design.
    """
    if not message or not message.strip():
        return None

    api_key = (tenant.anthropic_api_key if tenant else None) or settings.anthropic_api_key
    if not api_key:
        logger.warning(
            "Intent classifier skipped: no Anthropic API key for tenant %s",
            getattr(tenant, "id", None),
        )
        return None

    # Deferred import — agent_models pulls in tool_executor which cycles
    # back through chat_tools. The defer is harmless: classify() is only
    # called from request paths, never at module load.
    from app.services.agent_models import (
        SEAM_ORCHESTRATOR_INTENT_DISAMBIG,
        resolve_model,
    )

    model = await resolve_model(db, tenant, SEAM_ORCHESTRATOR_INTENT_DISAMBIG)

    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": model,
                    "max_tokens": 200,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": message.strip()}],
                },
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(
            "Intent classifier HTTP error (tenant=%s, model=%s): %s",
            getattr(tenant, "id", None), model, exc,
        )
        return None

    latency_ms = int((time.monotonic() - started) * 1000)

    if response.status_code != 200:
        logger.warning(
            "Intent classifier non-200 (tenant=%s, status=%d, body=%s)",
            getattr(tenant, "id", None),
            response.status_code,
            response.text[:200],
        )
        return None

    try:
        data = response.json()
        raw = data["content"][0]["text"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Intent classifier malformed response: %s", exc)
        return None

    parsed = _parse_json_response(raw)
    if parsed is None:
        logger.warning(
            "Intent classifier returned non-JSON / invalid JSON: %r",
            raw[:200],
        )
        return None

    intent = parsed.get("intent")
    if intent not in _VALID_INTENTS:
        logger.warning(
            "Intent classifier returned unknown intent %r — discarding",
            intent,
        )
        return None

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    event_reference = parsed.get("event_reference")
    if isinstance(event_reference, str):
        event_reference = event_reference.strip() or None
    else:
        event_reference = None

    reasoning = parsed.get("reasoning")
    if isinstance(reasoning, str):
        reasoning = reasoning.strip() or None
    else:
        reasoning = None

    decision = IntentDecision(
        intent=intent,
        confidence=confidence,
        event_reference=event_reference,
        reasoning=reasoning,
        requires_confirmation=intent in _DESTRUCTIVE_INTENTS,
        raw_text=raw,
        latency_ms=latency_ms,
    )
    logger.info(
        "Intent classifier: tenant=%s intent=%s confidence=%.2f "
        "event_ref=%r latency_ms=%d",
        getattr(tenant, "id", None),
        decision.intent,
        decision.confidence,
        decision.event_reference,
        decision.latency_ms,
    )
    return decision


def _parse_json_response(raw: str) -> dict | None:
    """Robust JSON extraction — strips markdown fences if Haiku adds them
    despite the prompt rule, and only accepts dicts."""
    text = raw.strip()
    if text.startswith("```"):
        # Remove ```json / ``` opening fence
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
