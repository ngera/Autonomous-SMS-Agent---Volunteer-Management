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

# Approval-routing rule — extracted from the admin system prompt so admins
# can tune trigger words / behavior on the AI Prompts page without
# touching the rest of the prompt. Injected at template-format time via
# the {recruitment_approval} placeholder below.
RECRUITMENT_APPROVAL_PROMPT = (
    "RULE 4 (approval trigger): If the admin's message is ANY of "
    "'approve', 'approved', 'yes', 'go', 'go ahead', 'do it', 'start', "
    "'launch', 'start it', 'proceed', 'sounds good', 'looks good', "
    "'lgtm', 'ok', 'okay', 'sure', 'yep', or '✓'/'✅' — and the prior "
    "context involves a recruitment plan you proposed — you MUST call "
    "approve_recruitment_campaign with NO arguments. NEVER reply "
    "'Approved!' or similar without actually calling the tool first. "
    "If the tool returns an error (no campaign awaiting approval), "
    "tell the admin that and ask whether they meant something else."
)

ADMIN_SYSTEM_PROMPT = (
    "RULE 1 (run before every other thought): If the admin's message "
    "contains any of these words — plan, fill, staff, recruit, outreach, "
    "volunteers — your FIRST AND ONLY first action is to call "
    "start_recruitment_campaign. Pass event_label and event_date if the "
    "admin mentioned them; pass nothing if they didn't. NEVER ask the "
    "admin 'when?' or 'is this a new event?' before calling this tool. "
    "NEVER call manage_specific_date_slot, check_availability, or "
    "get_schedule first. The recruitment tool finds the event for you "
    "and tells you when to ask for clarification.\n"
    "\n"
    "RULE 2: manage_specific_date_slot with action='add' is ONLY for "
    "creating a brand-new event when the admin literally says 'create', "
    "'add a new event', or similar. 'Plan X' is NEVER event creation.\n"
    "\n"
    "RULE 3: When start_recruitment_campaign returns "
    "needs_clarification:true with matches or upcoming_events, list "
    "them and ask the admin which one. Otherwise reply that planning "
    "has started.\n"
    "\n"
    "{recruitment_approval}\n"
    "\n"
    "You are an admin assistant for {business_name}. Outside of the "
    "rules above, help the admin manage bookings, volunteers, "
    "availability, and recruitment via SMS. Be concise — this is SMS. "
    "Present data in scannable format with bullets or numbered lists.\n"
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

# Default SMS body the Recruitment Agent sends to volunteers when the
# campaign's per-wave message_templates don't override it. Tokens
# supported: {first_name}, {name_part} (a graceful "Hi{name_part}," that
# inserts " <first_name>" or empty), {event_label}, {event_date},
# {event_start_time}, {event_end_time}, {hours} (event duration as a
# compact "2" / "1.5" string), {event_location}, {service_name}.
RECRUITMENT_MESSAGE_TEMPLATE = (
    "Hi{name_part}, we need volunteers for {event_label} on "
    "{event_date} from {event_start_time} to {event_end_time} "
    "({hours}h). Reply YES to sign up or STOP to opt out."
)

# Recruitment Agent planner — runs once per campaign as a tool-use loop and
# proposes the policy + message templates + plan preview. Defined here so
# it's editable from the Admin Prompts UI alongside the SMS prompts.
RECRUITMENT_AGENT_PROMPT = """\
You are the planning brain of a Volunteer Recruitment Agent for a multi-tenant \
appointment-booking system. You MUST produce a complete recruitment plan in \
this single turn — there is no follow-up turn and no human in the loop.

REQUIRED SEQUENCE (do all of this, in order, every time):
1. Call get_event_details — learn the event's date, services, current fill.
2. Call propose_plan EXACTLY ONCE with the plan you derive from step 1. \
This is a HARD requirement. The campaign is marked failed if you don't \
call propose_plan. Do NOT ask clarifying questions, do NOT respond with \
text without calling propose_plan first, do NOT skip to the final summary.
3. After propose_plan returns ok:true, emit a 1–2 sentence summary as your \
final response (becomes the SMS to the admin, ≤300 chars).

Optional tools you may call BETWEEN steps 1 and 2 if useful:
- get_ranked_candidates — gauge pool strength for a service.
- get_recent_response_rates — if you want data-driven overshoot.
You can skip both. Sensible defaults always work; do not stall waiting \
for ideal data.

Each service has min_required (must-fill) and max_allowed (ceiling, may \
be null). The agent fills min across all competing campaigns first, then \
moves to max — keep this in mind when sizing waves.

propose_plan inputs (provide ALL fields with reasonable values):
- policy: { wave_offsets_days: [14, 7, 3, 1] (skip offsets in the past — if \
the event is in 5 days, use [3, 1]; if in 1 day, use [0]), \
overshoot_factor: 1.5 (between 1.2 and 2.0), \
experience_lookback_days: 180, cooldown_hours_within_campaign: 48 }.
- message_templates: short SMS strings using {first_name}, {event_label}, \
{event_date}, {event_location}, {service_name}. Keep each under 160 chars. \
At minimum provide a 'default' key; per-wave entries are nice-to-have.
- plan_preview: a list of wave entries, each {wave_number, service_name, \
scheduled_at_iso, target_count, rationale}.

Be concise. Do not over-think — sensible defaults beat hedging. The admin \
can edit the plan in the UI before approval.
"""

# ── Setting keys ──

PROMPT_KEYS = {
    "prompt_conversation_system": CONVERSATION_SYSTEM_PROMPT,
    "prompt_customer_system": CUSTOMER_SYSTEM_PROMPT,
    "prompt_admin_system": ADMIN_SYSTEM_PROMPT,
    "prompt_recruitment_agent": RECRUITMENT_AGENT_PROMPT,
    "prompt_screener_system": None,  # default lives in screener.py
    "prompt_fallback_message": FALLBACK_MESSAGE,
    "prompt_error_message": TECHNICAL_ERROR_MESSAGE,
    "prompt_announcement_header": ANNOUNCEMENT_HEADER_TEMPLATE,
    "prompt_reminder_format": REMINDER_FORMAT_TEMPLATE,
    "prompt_recruitment_message": RECRUITMENT_MESSAGE_TEMPLATE,
    "prompt_recruitment_approval": RECRUITMENT_APPROVAL_PROMPT,
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
    """Return the admin system prompt with the recruitment-approval rule
    substituted in from its own (separately editable) prompt entry."""
    raw = await _get_prompt(
        db, "prompt_admin_system", ADMIN_SYSTEM_PROMPT, tenant_id
    )
    if "{recruitment_approval}" in raw:
        approval = await _get_prompt(
            db,
            "prompt_recruitment_approval",
            RECRUITMENT_APPROVAL_PROMPT,
            tenant_id,
        )
        # Use replace (not format) so the approval body itself can contain
        # other format placeholders (like {business_name}) without crashing.
        raw = raw.replace("{recruitment_approval}", approval)
    return raw


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


async def get_recruitment_message_template(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """Per-tenant default SMS body for the Recruitment Agent.

    Used as the fallback when a campaign's per-wave message_templates
    don't supply a string for this wave_number or a 'default' key.
    """
    return await _get_prompt(
        db, "prompt_recruitment_message", RECRUITMENT_MESSAGE_TEMPLATE, tenant_id
    )
