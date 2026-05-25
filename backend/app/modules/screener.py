"""Two-stage pre-screener for inbound SMS messages.

Stage 1: Rule-based (zero cost) — catches empty, garbage, prompt injection, opt-out
Stage 2: AI micro-prompt (~60-100 tokens) — classifies as RELEVANT/IRRELEVANT/ABUSIVE
"""

import re
import uuid
from dataclasses import dataclass
from enum import Enum

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.tenant import Tenant

logger = get_logger("screener")


class Classification(str, Enum):
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    ABUSIVE = "ABUSIVE"


class ScreenerMethod(str, Enum):
    RULE_BASED = "rule_based"
    AI_MICRO_PROMPT = "ai_micro_prompt"


@dataclass
class ScreenerResult:
    classification: Classification
    method: ScreenerMethod
    is_opt_out: bool = False


# Opt-out keywords (checked before classification)
OPT_OUT_KEYWORDS = {
    "stop", "unsubscribe", "opt out", "optout", "remove me",
    "do not contact", "leave me alone", "no more messages", "cancel messages",
}

# Prompt injection patterns
INJECTION_PATTERNS = re.compile(
    r"ignore\s*(all\s*)?(previous\s*)?instructions|"
    r"you\s+are\s+now|"
    r"pretend\s+you|"
    r"disregard\s*(all\s*)?(previous\s*)?|"
    r"forget\s*(all\s*)?(previous\s*)?instructions|"
    r"new\s+instructions|"
    r"system\s*prompt|"
    r"jailbreak",
    re.IGNORECASE,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsageSource
from app.prompts.screener import SCREENER_SYSTEM_PROMPT, get_screener_prompt
from app.services.token_usage import record_token_usage


# Patterns that indicate the assistant explicitly invited an open-ended
# reply on the previous turn — used by the contextual-reply bypass. If
# the most recent assistant turn ends with "?" OR contains one of these
# phrases, a brief volunteer reply (even "anything", "whatever", "idk")
# is almost certainly a contextual answer and must NOT be IRRELEVANT-struck.
# Lowercased substring match.
_ASSISTANT_QUESTION_PHRASES = (
    "let me know",
    "tell me",
    "what are you",
    "what would you",
    "what's your",
    "whats your",
    "what kind",
    "what time",
    "what day",
    "what date",
    "what works",
    "which ",
    "would you like",
    "are you interested",
    "are you available",
    "interested in",
    "any preference",
    "do you prefer",
)

# Profanity / slur indicators that override the contextual-reply bypass —
# we never want a short profanity to slip through just because the bot
# asked a question on the previous turn. Stage 2 still owns the nuanced
# call; this is a narrow blocklist for the bypass path only.
_BYPASS_BLOCKLIST = (
    "fuck", "shit", "bitch", "asshole", "cunt", "dick", "piss off",
    "screw you", "go to hell", "fck", "f u", "fu ",
)


def _assistant_invited_open_reply(history: list[dict] | None) -> bool:
    """True if the most recent assistant message looks like an invitation
    for the volunteer to reply with anything they want — a question, an
    open prompt, or a phrase that solicits input. Used to safely bypass
    Haiku for short replies that would otherwise risk a false IRRELEVANT.
    """
    if not history:
        return False
    # Walk backward to find the most recent assistant message
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        content = (msg.get("content") or "").strip().lower()
        if not content:
            return False
        # Strip trailing emoji/whitespace before the `?` check — assistants
        # often append a smile after the question mark.
        stripped = content.rstrip(" 😊🙂👍✨💪🎉.,!").rstrip()
        if stripped.endswith("?"):
            return True
        return any(p in content for p in _ASSISTANT_QUESTION_PHRASES)
    return False


def stage1_rule_based(
    message: str,
    conversation_history: list[dict] | None = None,
) -> ScreenerResult | None:
    """Stage 1: Rule-based screening (zero cost).

    Returns a ScreenerResult if a rule matches, None to pass to Stage 2.

    ``conversation_history`` enables the contextual-reply bypass: when
    the most recent assistant turn invited an open reply, any short
    volunteer message (that isn't profanity or prompt-injection) is
    classified RELEVANT here so it can't be misjudged by Haiku.
    """
    text = message.strip()
    text_lower = text.lower()

    # Check opt-out keywords first
    for keyword in OPT_OUT_KEYWORDS:
        if keyword in text_lower:
            return ScreenerResult(
                classification=Classification.RELEVANT,
                method=ScreenerMethod.RULE_BASED,
                is_opt_out=True,
            )

    # Empty message — hard reject. Single-character replies like "1", "y", "n"
    # are intentionally allowed through to stage 2 because they are common
    # contextual answers (e.g. "Reply with 1, 2, or 3 to pick a slot").
    if len(text) == 0:
        return ScreenerResult(
            classification=Classification.IRRELEVANT,
            method=ScreenerMethod.RULE_BASED,
        )

    # Garbage characters (>85% non-alphabetic). Short replies like "1", "12:00",
    # "9pm" can have low alpha ratios but be perfectly relevant in context, so
    # only apply this heuristic to longer messages where pure noise is a
    # plausible interpretation.
    if len(text) >= 8:
        alpha_count = sum(1 for c in text if c.isalpha())
        if (alpha_count / len(text)) < 0.15:
            return ScreenerResult(
                classification=Classification.IRRELEVANT,
                method=ScreenerMethod.RULE_BASED,
            )

    # Prompt injection patterns — checked BEFORE the contextual bypass so
    # a jailbreak attempt right after an assistant question still trips.
    if INJECTION_PATTERNS.search(text):
        return ScreenerResult(
            classification=Classification.ABUSIVE,
            method=ScreenerMethod.RULE_BASED,
        )

    # Contextual-reply bypass: brief reply right after the assistant
    # invited open input → RELEVANT without a Haiku call. Protects against
    # the failure mode where a volunteer replies "anything"/"whatever"/
    # "you pick" and Haiku misclassifies it as IRRELEVANT because the
    # word in isolation doesn't look booking-related.
    #
    # Bounds: ≤ 30 chars (short reply), no profanity (would otherwise
    # need ABUSIVE judgment from Stage 2), prior assistant turn solicited
    # input. Otherwise fall through to Stage 2 as before.
    if (
        len(text) <= 30
        and conversation_history
        and _assistant_invited_open_reply(conversation_history)
        and not any(b in text_lower for b in _BYPASS_BLOCKLIST)
    ):
        return ScreenerResult(
            classification=Classification.RELEVANT,
            method=ScreenerMethod.RULE_BASED,
        )

    # No rule matched — pass to Stage 2
    return None


async def stage2_ai_classify(
    message: str, db: AsyncSession | None = None, tenant: Tenant | None = None,
    contact_id: "uuid.UUID | None" = None, contact_phone: str | None = None,
    conversation_history: list[dict] | None = None,
) -> ScreenerResult:
    """Stage 2: AI micro-prompt classification (~60-100 tokens).

    When conversation_history is provided, includes recent context so that
    short contextual replies (e.g. "yes", "tomorrow") are not misclassified.
    On API error, defaults to RELEVANT to avoid blocking legitimate users.
    """
    api_key = tenant.anthropic_api_key if tenant else settings.anthropic_api_key

    try:
        prompt = await get_screener_prompt(db) if db else SCREENER_SYSTEM_PROMPT

        # Build messages with conversation context if available
        api_messages: list[dict] = []
        if conversation_history:
            # Include the last few turns for context (keep token usage low)
            recent = conversation_history[-6:]
            context_lines = []
            for msg in recent:
                role_label = "Volunteer" if msg.get("role") == "user" else "Assistant"
                context_lines.append(f"{role_label}: {msg.get('content', '')}")
            context_text = "\n".join(context_lines)
            api_messages.append({
                "role": "user",
                "content": (
                    f"Recent conversation context:\n{context_text}\n\n"
                    f"New message to classify: {message}"
                ),
            })
        else:
            api_messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 10,
                    "messages": api_messages,
                    "system": prompt,
                },
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=5.0,
            )

        if response.status_code != 200:
            logger.warning("Anthropic screener API error: %d", response.status_code)
            return ScreenerResult(
                classification=Classification.RELEVANT,
                method=ScreenerMethod.AI_MICRO_PROMPT,
            )

        data = response.json()

        # Record token usage for screener
        usage = data.get("usage", {})
        if db and tenant:
            await record_token_usage(
                db=db,
                tenant_id=tenant.id,
                source=TokenUsageSource.SCREENER,
                model="claude-haiku-4-5-20251001",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                contact_id=contact_id,
                contact_phone=contact_phone,
            )

        raw_text = data["content"][0]["text"].strip().strip(".").upper()

        if raw_text in ("RELEVANT", "IRRELEVANT", "ABUSIVE"):
            return ScreenerResult(
                classification=Classification(raw_text),
                method=ScreenerMethod.AI_MICRO_PROMPT,
            )

        # Unrecognized response — default to RELEVANT
        logger.warning("Unexpected screener response: %s", raw_text)
        return ScreenerResult(
            classification=Classification.RELEVANT,
            method=ScreenerMethod.AI_MICRO_PROMPT,
        )

    except Exception as e:
        logger.error("Screener AI error: %s", str(e))
        return ScreenerResult(
            classification=Classification.RELEVANT,
            method=ScreenerMethod.AI_MICRO_PROMPT,
        )


async def screen_message(
    message: str, db: AsyncSession | None = None, tenant: Tenant | None = None,
    contact_id: "uuid.UUID | None" = None, contact_phone: str | None = None,
    conversation_history: list[dict] | None = None,
) -> ScreenerResult:
    """Run the full two-stage screening pipeline."""
    # Stage 1 — pass history so the contextual-reply bypass can fire
    # when the assistant just invited an open answer.
    result = stage1_rule_based(message, conversation_history=conversation_history)
    if result is not None:
        return result

    # Stage 2
    return await stage2_ai_classify(
        message, db, tenant=tenant,
        contact_id=contact_id, contact_phone=contact_phone,
        conversation_history=conversation_history,
    )
