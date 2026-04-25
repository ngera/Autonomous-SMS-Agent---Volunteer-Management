"""Long-term memory extraction for completed conversations.

After a customer conversation closes (booking confirmed), call Claude
once to merge the transcript into a durable structured profile +
free-form notes on the Contact. Runs as a background task — never on
the SMS response path.
"""

import json
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsageSource
from app.modules.tool_executor import ANTHROPIC_API_URL, ANTHROPIC_VERSION, DEFAULT_MODEL
from app.services.token_usage import record_token_usage

logger = get_logger("memory_extraction")

NOTES_MAX_CHARS = 1000

EXTRACTION_PROMPT = """You are extracting durable facts about a customer from a completed booking conversation.

Existing memory for this customer:
PREFERENCES (JSON): {existing_preferences}
NOTES: {existing_notes}

Conversation transcript:
{transcript}

Return ONLY valid JSON matching this shape — no prose, no markdown fences:
{{
  "preferences": {{
    "preferred_days": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"] or null,
    "preferred_time_of_day": "morning" or "afternoon" or "evening" or null,
    "preferred_services": ["service name", ...] or null,
    "communication_style": "brief" or "chatty" or null
  }},
  "notes": "Merged free-form facts under 800 chars. Only include things that will matter for FUTURE bookings (allergies, accessibility needs, recurring constraints, family relationships, important context the customer mentioned). DO NOT include one-off booking details like the date/time of this specific booking."
}}

Rules:
- MERGE with existing memory — don't drop facts unless the new conversation contradicts them.
- If the conversation contained nothing memorable, return the existing values unchanged.
- Omit fields you can't infer (use null), don't invent.
- Output JSON only.
"""


def _format_transcript(message_history: list[dict]) -> str:
    """Render the message history as plain dialogue for the prompt."""
    lines = []
    for msg in message_history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        speaker = "Customer" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


async def extract_and_save_memory(
    contact_id: uuid.UUID,
    tenant_id: uuid.UUID,
    message_history: list[dict],
) -> None:
    """Run extraction in its own DB session — safe to call from BackgroundTasks."""
    if not message_history:
        return

    async with async_session_factory() as db:
        try:
            await _run_extraction(db, contact_id, tenant_id, message_history)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("Memory extraction failed for contact %s: %s", contact_id, e)


async def _run_extraction(
    db: AsyncSession,
    contact_id: uuid.UUID,
    tenant_id: uuid.UUID,
    message_history: list[dict],
) -> None:
    contact = (
        await db.execute(select(Contact).where(Contact.id == contact_id))
    ).scalar_one_or_none()
    if not contact:
        return

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        return

    api_key = tenant.anthropic_api_key or settings.anthropic_api_key
    if not api_key:
        logger.warning("No Anthropic API key for tenant %s — skipping extraction", tenant_id)
        return

    prompt = EXTRACTION_PROMPT.format(
        existing_preferences=json.dumps(contact.preferences) if contact.preferences else "null",
        existing_notes=contact.notes or "(none)",
        transcript=_format_transcript(message_history),
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ANTHROPIC_API_URL,
                json={
                    "model": DEFAULT_MODEL,
                    "max_tokens": 400,
                    "system": "You extract structured customer memory from booking conversations. Output JSON only.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
                timeout=20.0,
            )
    except Exception as e:
        logger.error("Anthropic call failed during memory extraction: %s", e)
        return

    if response.status_code != 200:
        logger.error("Memory extraction API error %d: %s", response.status_code, response.text[:200])
        return

    data = response.json()
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    text = text.strip()

    parsed = _parse_json_object(text)
    if not parsed:
        logger.warning("Could not parse extraction output for contact %s: %s", contact_id, text[:200])
        return

    new_prefs = parsed.get("preferences")
    new_notes = parsed.get("notes")

    if isinstance(new_prefs, dict):
        cleaned = {k: v for k, v in new_prefs.items() if v not in (None, [], "")}
        contact.preferences = cleaned or None

    if isinstance(new_notes, str):
        contact.notes = new_notes.strip()[:NOTES_MAX_CHARS] or None

    from datetime import datetime, timezone
    contact.memory_updated_at = datetime.now(timezone.utc)

    usage = data.get("usage", {})
    await record_token_usage(
        db=db,
        tenant_id=tenant_id,
        source=TokenUsageSource.CONVERSATION,
        model=data.get("model", DEFAULT_MODEL),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        contact_id=contact_id,
        contact_phone=contact.phone,
    )

    logger.info("Updated long-term memory for contact %s", contact_id)


def _parse_json_object(text: str) -> dict | None:
    """Best-effort parse — strips markdown fences if present."""
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None
