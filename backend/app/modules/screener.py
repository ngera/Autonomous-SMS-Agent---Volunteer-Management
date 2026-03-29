"""Two-stage pre-screener for inbound SMS messages.

Stage 1: Rule-based (zero cost) — catches empty, garbage, prompt injection, opt-out
Stage 2: AI micro-prompt (~60-100 tokens) — classifies as RELEVANT/IRRELEVANT/ABUSIVE
"""

import re
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

from app.prompts.screener import SCREENER_SYSTEM_PROMPT, get_screener_prompt


def stage1_rule_based(message: str) -> ScreenerResult | None:
    """Stage 1: Rule-based screening (zero cost).

    Returns a ScreenerResult if a rule matches, None to pass to Stage 2.
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

    # Empty or near-empty message
    if len(text) < 2:
        return ScreenerResult(
            classification=Classification.IRRELEVANT,
            method=ScreenerMethod.RULE_BASED,
        )

    # Garbage characters (>85% non-alphabetic)
    alpha_count = sum(1 for c in text if c.isalpha())
    if len(text) > 0 and (alpha_count / len(text)) < 0.15:
        return ScreenerResult(
            classification=Classification.IRRELEVANT,
            method=ScreenerMethod.RULE_BASED,
        )

    # Prompt injection patterns
    if INJECTION_PATTERNS.search(text):
        return ScreenerResult(
            classification=Classification.ABUSIVE,
            method=ScreenerMethod.RULE_BASED,
        )

    # No rule matched — pass to Stage 2
    return None


async def stage2_ai_classify(
    message: str, db: AsyncSession | None = None, tenant: Tenant | None = None,
) -> ScreenerResult:
    """Stage 2: AI micro-prompt classification (~60-100 tokens).

    On API error, defaults to RELEVANT to avoid blocking legitimate users.
    """
    api_key = tenant.anthropic_api_key if tenant else settings.anthropic_api_key

    try:
        prompt = await get_screener_prompt(db) if db else SCREENER_SYSTEM_PROMPT
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": "claude-haiku-4-5-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": message}],
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
) -> ScreenerResult:
    """Run the full two-stage screening pipeline."""
    # Stage 1
    result = stage1_rule_based(message)
    if result is not None:
        return result

    # Stage 2
    return await stage2_ai_classify(message, db, tenant=tenant)
