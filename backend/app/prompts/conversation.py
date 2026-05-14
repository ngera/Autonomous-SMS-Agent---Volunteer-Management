"""Prompts for the AI conversation booking engine."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ── Default prompts (used when no DB override exists) ──

# Legacy prompt-stuffing template (kept for reference / rollback)
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

# ── Lightweight tool_use prompts ──

CUSTOMER_SYSTEM_PROMPT = (
    "You are a friendly volunteer scheduling assistant for {business_name}.\n"
    "Help volunteers sign up for, reschedule, and cancel their volunteer shifts via SMS.\n"
    "Use the provided tools to check availability, look up information, and take actions.\n"
    "Never guess or suggest specific service names — always call list_services first to get the actual offerings.\n"
    "The volunteer can only see and book services they are registered to participate in.\n"
    "Be conversational and concise — this is SMS, keep messages short.\n"
    "Never share internal IDs or technical details with the volunteer.\n"
    "Show times in a friendly format (e.g., \"Friday April 3rd at 9:00 AM\").\n"
    "When showing availability, mention how many spots are remaining and if more people are needed to meet the minimum.\n"
    "After booking, confirm the service, date/time, and booking reference number (ref).\n"
    "When a booking is created, rescheduled, or cancelled, the tool response includes a calendar_link and a ref.\n"
    "Always share the ref and calendar_link with the volunteer so they can add/update/remove it from their calendar.\n"
    "OVERLAPPING BOOKINGS:\n"
    "- A volunteer can only be in one place at a time. If the services they want to sign up for have overlapping start/end times, do NOT book any of them silently.\n"
    "- If the volunteer asks to sign up for two or more services in one message and their times overlap, do NOT call book_appointment yet. List the services with their times, point out the overlap, and ask which one they want to book. Only call book_appointment after they pick.\n"
    "- If book_appointment returns an overlap error against an existing booking, tell the volunteer which existing booking conflicts (service name, time) and ask whether they'd like to cancel that existing booking, pick a different time, or skip the new one. Do not auto-cancel or auto-book.\n"
    "{custom_instructions}"
)

ADMIN_SYSTEM_PROMPT = (
    "You are an admin assistant for {business_name}.\n"
    "Help the admin manage bookings, volunteers, and availability via SMS.\n"
    "Use the provided tools to look up information and take actions.\n"
    "Be concise — this is SMS. Present data in a clear, scannable format.\n"
    "Use bullet points or numbered lists for multiple items.\n"
    "{custom_instructions}"
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

ANNOUNCEMENT_HEADER_TEMPLATE = (
    "[{event_label} on {event_date} at {event_start_time}{event_location_part}]\n\n"
)

REMINDER_FORMAT_TEMPLATE = (
    "We still need volunteers for {service_name} on {date}. Reply to sign up for a time slot!"
)

# ── Setting keys ──

PROMPT_KEYS = {
    "prompt_conversation_system": CONVERSATION_SYSTEM_PROMPT,
    "prompt_customer_system": CUSTOMER_SYSTEM_PROMPT,
    "prompt_admin_system": ADMIN_SYSTEM_PROMPT,
    "prompt_screener_system": None,  # default lives in screener.py
    "prompt_fallback_message": FALLBACK_MESSAGE,
    "prompt_error_message": TECHNICAL_ERROR_MESSAGE,
    "prompt_announcement_header": ANNOUNCEMENT_HEADER_TEMPLATE,
    "prompt_reminder_format": REMINDER_FORMAT_TEMPLATE,
}


# ── DB-aware getters ──

async def _get_prompt(
    db: AsyncSession, key: str, default: str, tenant_id: uuid.UUID | None = None,
) -> str:
    from app.models.system_setting import SystemSetting

    query = select(SystemSetting).where(SystemSetting.key == key)
    if tenant_id:
        query = query.where(SystemSetting.tenant_id == tenant_id)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def get_conversation_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(db, "prompt_conversation_system", CONVERSATION_SYSTEM_PROMPT, tenant_id)


async def get_customer_system_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(db, "prompt_customer_system", CUSTOMER_SYSTEM_PROMPT, tenant_id)


async def get_admin_system_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(db, "prompt_admin_system", ADMIN_SYSTEM_PROMPT, tenant_id)


async def get_fallback_message(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(db, "prompt_fallback_message", FALLBACK_MESSAGE, tenant_id)


async def get_error_message(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(db, "prompt_error_message", TECHNICAL_ERROR_MESSAGE, tenant_id)


async def get_announcement_header_template(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(
        db, "prompt_announcement_header", ANNOUNCEMENT_HEADER_TEMPLATE, tenant_id
    )


async def get_reminder_format_template(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    return await _get_prompt(
        db, "prompt_reminder_format", REMINDER_FORMAT_TEMPLATE, tenant_id
    )
