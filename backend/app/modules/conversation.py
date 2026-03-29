"""AI conversation engine for SMS booking dialogue.

Uses Claude claude-haiku-4-5 with dynamic context injection for natural-language
appointment booking conversations.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.related_service import RelatedService
from app.models.system_setting import SystemSetting
from app.models.tenant import Tenant
from app.prompts.conversation import (
    get_conversation_prompt,
    get_error_message,
    get_fallback_message,
)
from app.services.availability import compute_available_slots

logger = get_logger("conversation")

# Regex to extract booking confirmation signal from AI response
BOOKING_SIGNAL_PATTERN = re.compile(
    r"BOOKING_CONFIRMED:([a-f0-9\-]+):(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s]*):(\d+\.?\d*)"
)


@dataclass
class ConversationResponse:
    """Result from the conversation AI."""
    message_to_user: str
    booking_confirmed: bool = False
    appointment_type_id: uuid.UUID | None = None
    slot_datetime: datetime | None = None
    total_price: float | None = None


async def build_system_prompt(
    db: AsyncSession, contact_phone: str, tenant: Tenant | None = None,
) -> str:
    """Build the dynamic system prompt with live data."""
    tenant_id = tenant.id if tenant else None
    business_name = tenant.business_name if tenant else settings.business_name

    # Custom instructions
    custom_instructions = ""
    setting_query = select(SystemSetting).where(SystemSetting.key == "custom_ai_instructions")
    if tenant_id:
        setting_query = setting_query.where(SystemSetting.tenant_id == tenant_id)
    setting_result = await db.execute(setting_query)
    setting = setting_result.scalar_one_or_none()
    if setting:
        custom_instructions = setting.value

    # Active appointment types
    types_query = select(AppointmentType).where(AppointmentType.is_active.is_(True))
    if tenant_id:
        types_query = types_query.where(AppointmentType.tenant_id == tenant_id)
    types_result = await db.execute(types_query)
    appt_types = types_result.scalars().all()
    types_text = "\n".join(
        f"- {t.name}: {t.duration_minutes} min, £{t.price:.2f}"
        + (f" — {t.description}" if t.description else "")
        for t in appt_types
    )

    # Related services
    related_query = select(RelatedService)
    if tenant_id:
        related_query = related_query.where(RelatedService.tenant_id == tenant_id)
    related_result = await db.execute(related_query)
    related_services = related_result.scalars().all()
    related_text = ""
    if related_services:
        lines = []
        for rs in related_services:
            primary = next((t for t in appt_types if t.id == rs.appointment_type_id), None)
            related = next((t for t in appt_types if t.id == rs.related_appointment_type_id), None)
            if primary and related:
                lines.append(
                    f"- When customer selects '{primary.name}', suggest '{related.name}': "
                    f"{rs.suggestion_message}"
                )
        related_text = "\n".join(lines)

    # Available slots (next 14 days) — compute a summary
    from datetime import date

    today = date.today()
    slots_summary_lines = []
    for day_offset in range(14):
        check_date = today + timedelta(days=day_offset)
        for appt_type in appt_types[:3]:  # Limit to avoid excessive API calls
            try:
                slots = await compute_available_slots(
                    db, check_date, str(appt_type.id), max_slots=3, tenant=tenant,
                )
                if slots:
                    for s in slots:
                        slot_str = s["start"].strftime("%A %d %B at %I:%M%p")
                        slots_summary_lines.append(f"- {appt_type.name}: {slot_str}")
            except Exception:
                pass
        if len(slots_summary_lines) >= 9:
            break

    slots_text = "\n".join(slots_summary_lines[:9]) if slots_summary_lines else "No slots currently available."

    # Customer history
    history_text = "New customer — no previous bookings."
    bookings_query = (
        select(Booking)
        .where(Booking.contact_phone == contact_phone)
        .order_by(Booking.scheduled_at.desc())
        .limit(5)
    )
    if tenant_id:
        bookings_query = bookings_query.where(Booking.tenant_id == tenant_id)
    bookings_result = await db.execute(bookings_query)
    bookings = bookings_result.scalars().all()
    if bookings:
        lines = []
        for b in bookings:
            appt = next((t for t in appt_types if t.id == b.appointment_type_id), None)
            name = appt.name if appt else "Unknown"
            lines.append(f"- {name} on {b.scheduled_at.strftime('%d %B %Y')} ({b.status.value})")
        history_text = "Returning customer:\n" + "\n".join(lines)

    prompt_template = await get_conversation_prompt(db)
    return prompt_template.format(
        business_name=business_name,
        types_text=types_text,
        related_text=related_text or "None configured.",
        slots_text=slots_text,
        custom_instructions=custom_instructions or "None.",
        history_text=history_text,
    )


async def get_ai_response(
    db: AsyncSession,
    contact_phone: str,
    message_history: list[dict],
    user_message: str,
    tenant: Tenant | None = None,
) -> ConversationResponse:
    """Call Claude claude-haiku-4-5 for a conversation turn.

    Retries once on failure, then returns a fallback message.
    """
    system_prompt = await build_system_prompt(db, contact_phone, tenant=tenant)

    api_key = tenant.anthropic_api_key if tenant else settings.anthropic_api_key

    # Build messages for the API
    api_messages = []
    for msg in message_history:
        api_messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })
    api_messages.append({"role": "user", "content": user_message})

    for attempt in range(2):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json={
                        "model": "claude-haiku-4-5-20241022",
                        "max_tokens": 500,
                        "system": system_prompt,
                        "messages": api_messages,
                    },
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    timeout=15.0,
                )

            if response.status_code == 200:
                data = response.json()
                ai_text = data["content"][0]["text"]
                return _parse_ai_response(ai_text)

            logger.warning(
                "Anthropic conversation API error (attempt %d): %d",
                attempt + 1, response.status_code,
            )

        except Exception as e:
            logger.error("Conversation AI error (attempt %d): %s", attempt + 1, str(e))

        if attempt == 0:
            await asyncio.sleep(1)

    # Both attempts failed
    error_msg = await get_error_message(db)
    return ConversationResponse(message_to_user=error_msg)


def _parse_ai_response(ai_text: str) -> ConversationResponse:
    """Parse the AI response, extracting any booking confirmation signal."""
    match = BOOKING_SIGNAL_PATTERN.search(ai_text)

    if match:
        type_id = uuid.UUID(match.group(1))
        slot_dt = datetime.fromisoformat(match.group(2))
        price = float(match.group(3))

        # Remove the signal from the user-facing message
        clean_message = BOOKING_SIGNAL_PATTERN.sub("", ai_text).strip()

        return ConversationResponse(
            message_to_user=clean_message,
            booking_confirmed=True,
            appointment_type_id=type_id,
            slot_datetime=slot_dt,
            total_price=price,
        )

    return ConversationResponse(message_to_user=ai_text)
