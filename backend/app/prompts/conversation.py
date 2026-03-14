"""Prompts for the AI conversation booking engine."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ── Default prompts (used when no DB override exists) ──

CONVERSATION_SYSTEM_PROMPT = (
    "You are a friendly appointment booking assistant for {business_name}.\n\n"
    "APPOINTMENT TYPES:\n{types_text}\n\n"
    "RELATED SERVICES:\n{related_text}\n\n"
    "AVAILABLE SLOTS (next 14 days):\n{slots_text}\n\n"
    "CUSTOMER HISTORY:\n{history_text}\n\n"
    "CUSTOM INSTRUCTIONS:\n{custom_instructions}\n\n"
    "Rules:\n"
    "- Only discuss appointments and booking.\n"
    "- Be conversational and friendly.\n"
    "- Guide the customer through: type selection → related service suggestion → "
    "slot selection → price confirmation → final confirmation.\n"
    "- Present up to 3 available slots at a time.\n"
    "- When the customer confirms a booking, output exactly on its own line:\n"
    "BOOKING_CONFIRMED:{{appointment_type_id}}:{{slot_datetime_iso}}:{{total_price}}\n"
    "- The BOOKING_CONFIRMED line will be stripped before sending to the customer.\n"
    "- Never show the BOOKING_CONFIRMED signal to the customer.\n"
)

FALLBACK_MESSAGE = (
    "I'm sorry, I'm having trouble understanding. "
    "You can:\n"
    "1. Book an appointment\n"
    "2. Reschedule an existing appointment\n"
    "3. Cancel an appointment\n\n"
    "Or contact us directly for assistance."
)

TECHNICAL_ERROR_MESSAGE = (
    "Sorry, I'm having a technical issue. Please try again shortly."
)

# ── Setting keys ──

PROMPT_KEYS = {
    "prompt_conversation_system": CONVERSATION_SYSTEM_PROMPT,
    "prompt_screener_system": None,  # default lives in screener.py
    "prompt_fallback_message": FALLBACK_MESSAGE,
    "prompt_error_message": TECHNICAL_ERROR_MESSAGE,
}


# ── DB-aware getters ──

async def _get_prompt(db: AsyncSession, key: str, default: str) -> str:
    from app.models.system_setting import SystemSetting

    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def get_conversation_prompt(db: AsyncSession) -> str:
    return await _get_prompt(db, "prompt_conversation_system", CONVERSATION_SYSTEM_PROMPT)


async def get_fallback_message(db: AsyncSession) -> str:
    return await _get_prompt(db, "prompt_fallback_message", FALLBACK_MESSAGE)


async def get_error_message(db: AsyncSession) -> str:
    return await _get_prompt(db, "prompt_error_message", TECHNICAL_ERROR_MESSAGE)
