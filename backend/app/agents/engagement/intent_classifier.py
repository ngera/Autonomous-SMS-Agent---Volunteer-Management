"""Haiku-based intent classifier — Tier 2 of the volunteer engagement
hybrid intent stack.

Pipeline (mirrors the admin-side stack documented in
``memory/design_decisions.md`` #22):

  Tier 1  Deterministic regex routers in
          ``app.agents.engagement.intents.maybe_handle_*``.
          Free + instant. Covers canonical phrasings:
          "HERE", "DONE", "switch to kitchen", "also greeter", etc.

  Tier 2  THIS MODULE. Haiku JSON classifier. Catches the long tail
          regex misses: "im finally here lol", "leaving now", "moving
          over to setup actually", "switching back to runner". Adds
          ~200-500ms + ~$0.0001/call. Fires only when Tier 1 returned
          ``None``.

  Tier 3  Full customer LLM with tools (``run_tool_conversation``).
          Handles open-ended questions and multi-turn flows.

Guardrails:
  - Confidence threshold (``CONFIDENCE_THRESHOLD``) — below it we
    fall through to the LLM rather than acting on a guess. Volunteer
    misclassification at T0 of an event means the admin thinks the
    volunteer no-showed; the cost asymmetry favors caution.
  - Soft-fail on API error — return ``None`` and let the full LLM
    handle it. Don't block an arrival on a Haiku outage.
  - SWITCH/ALSO require a non-empty ``service_reference`` — without
    one, we can't synthesize a phrase the regex router accepts, so we
    fall through.
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

logger = get_logger("engagement.intent_classifier")


# Volunteer intents are non-destructive (you can re-text HERE if check-in
# was wrong), so the bar can be slightly lower than the admin classifier.
# Still high enough that "I might leave soon" doesn't trigger DONE.
CONFIDENCE_THRESHOLD = 0.75

_HTTP_TIMEOUT_SECONDS = 4.0

_VALID_INTENTS = frozenset(
    {
        "here",          # checking in for the first time
        "reentry",       # returning after a previous check-out (HERE-AGAIN/BACK)
        "done",          # checking out / leaving
        "switch",        # ending current service, starting another
        "also",          # adding a parallel service alongside the current one
        "other",         # everything else — fall through to LLM
    }
)


_SYSTEM_PROMPT = """You are an intent classifier for inbound SMS from \
volunteers at an event. Classify the volunteer's message into ONE intent \
and return STRICT JSON.

Valid intents:
- "here"      Volunteer is checking in / arriving at the event for the first time
- "reentry"   Volunteer is returning after previously checking out (came back)
- "done"      Volunteer is checking out / leaving / finished their shift
- "switch"    Volunteer is ending their current service and switching to a different one
- "also"      Volunteer wants to ADD a second service in parallel with the one they're already doing
- "other"     Anything else: questions, greetings, off-topic, ambiguous, multi-intent

Rules:
1. Output JSON only. No prose, no markdown fence. Schema:
   {"intent": "<one of above>", "confidence": <0.0..1.0>, "service_reference": "<phrase or null>", "reasoning": "<one short sentence>"}
2. "service_reference" is the noun phrase identifying the service for "switch" and "also" intents (e.g. "kitchen prep", "setup", "runner"). For "switch" and "also" without an explicit service in the message, set service_reference to null AND lower confidence below 0.7 — the regex router relies on the service name to act.
3. "confidence" is your honest self-assessed probability. Be calibrated — use < 0.75 when the message is ambiguous, hypothetical ("might leave"), or could plausibly mean something else.
4. Prefer "other" when uncertain. The cost of a false positive on "done" or "here" is high: the admin sees a phantom check-in / no-show.
5. "here" vs "reentry": "reentry" requires explicit language about coming back ("im back", "returning", "back at it"). Default to "here" when unclear — the dispatcher will detect prior check-out and convert automatically.
6. "switch" vs "also": "switch" replaces the current service ("moving to setup", "changing to runner"). "also" adds a parallel one ("doing greeter too", "also helping with cleanup").
7. "done" requires committed/completed language ("leaving", "heading out", "all done", "im out", "finished"). Tentative phrases ("might leave soon", "almost done") should be "other".
8. Greetings, thanks, questions ("what time?", "where do I park?"), confirmations ("sounds good"), and off-topic messages are "other"."""


@dataclass(frozen=True)
class EngagementIntentDecision:
    intent: str
    confidence: float
    service_reference: str | None
    reasoning: str | None
    raw_text: str | None
    latency_ms: int


async def classify(
    message: str,
    db: AsyncSession,
    tenant: Tenant,
) -> EngagementIntentDecision | None:
    """Classify a volunteer message via Haiku.

    Returns ``None`` on empty input, API failure, unparseable response,
    or unknown intent — caller falls through to the full LLM.
    """
    if not message or not message.strip():
        return None

    api_key = (tenant.anthropic_api_key if tenant else None) or settings.anthropic_api_key
    if not api_key:
        logger.warning(
            "Engagement classifier skipped: no Anthropic API key for tenant %s",
            getattr(tenant, "id", None),
        )
        return None

    from app.services.agent_models import (
        SEAM_ENGAGEMENT_INTENT_ROUTER,
        resolve_model,
    )

    model = await resolve_model(db, tenant, SEAM_ENGAGEMENT_INTENT_ROUTER)

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
            "Engagement classifier HTTP error (tenant=%s, model=%s): %s",
            getattr(tenant, "id", None), model, exc,
        )
        return None

    latency_ms = int((time.monotonic() - started) * 1000)

    if response.status_code != 200:
        logger.warning(
            "Engagement classifier non-200 (tenant=%s, status=%d, body=%s)",
            getattr(tenant, "id", None),
            response.status_code,
            response.text[:200],
        )
        return None

    try:
        data = response.json()
        raw = data["content"][0]["text"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Engagement classifier malformed response: %s", exc)
        return None

    parsed = _parse_json_response(raw)
    if parsed is None:
        logger.warning(
            "Engagement classifier returned non-JSON / invalid JSON: %r",
            raw[:200],
        )
        return None

    intent = parsed.get("intent")
    if intent not in _VALID_INTENTS:
        logger.warning(
            "Engagement classifier returned unknown intent %r — discarding",
            intent,
        )
        return None

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    service_reference = parsed.get("service_reference")
    if isinstance(service_reference, str):
        service_reference = service_reference.strip() or None
    else:
        service_reference = None

    reasoning = parsed.get("reasoning")
    if isinstance(reasoning, str):
        reasoning = reasoning.strip() or None
    else:
        reasoning = None

    decision = EngagementIntentDecision(
        intent=intent,
        confidence=confidence,
        service_reference=service_reference,
        reasoning=reasoning,
        raw_text=raw,
        latency_ms=latency_ms,
    )
    logger.info(
        "Engagement classifier: tenant=%s intent=%s confidence=%.2f "
        "service_ref=%r latency_ms=%d",
        getattr(tenant, "id", None),
        decision.intent,
        decision.confidence,
        decision.service_reference,
        decision.latency_ms,
    )
    return decision


def _parse_json_response(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
