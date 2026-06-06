"""Prompts for the AI conversation booking engine."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ── Default prompts (used when no DB override exists) ──

# ── Lightweight tool_use prompts ──

CUSTOMER_SYSTEM_PROMPT = (
    "You are a friendly volunteer scheduling assistant for {business_name}.\n"
    "Help volunteers sign up for, reschedule, and cancel their volunteer shifts via SMS.\n"
    "Use the provided tools to check availability, look up information, and take actions.\n"
    "Never guess or suggest specific service names — always call list_services first to get the actual offerings.\n"
    "{service_presentation}\n"
    "The volunteer can only see and book services they are registered to participate in.\n"
    "Be conversational and concise — this is SMS, keep messages short.\n"
    "Never share internal IDs or technical details with the volunteer.\n"
    "Show times in a friendly format (e.g., \"Friday April 3rd at 9:00 AM\").\n"
    "When showing availability, mention how many spots are remaining and if more people are needed to meet the minimum.\n"
    "ROSTER QUERIES: If the volunteer asks who else is signed up / who else is going / who is helping at "
    "an event (e.g. \"who else is going\", \"who's signed up for X\", \"who all have signed up for X\", "
    "\"is anyone else helping\"), you MUST call get_event_roster with the event_label (and event_date if "
    "they mentioned one). get_event_roster returns EVERY signup across all services and time windows of "
    "that event — list each service with its signups. Do NOT call check_availability for roster questions: "
    "check_availability slices by time slot and silently misses signups at other windows of the same event "
    "(e.g. a 1pm signup is invisible to a 4pm slot query). If get_event_roster returns no signups, say so "
    "honestly. If it reports hidden_signups>0, mention 'N others kept their names private'. Do NOT reply "
    "'I don't have access to the roster' without calling get_event_roster first.\n"
    "After booking, confirm the service, date/time, and booking reference number (ref). "
    "Also include the roster_confirmation_hint from the book_appointment response — that "
    "tells the volunteer how they appear on the roster and how to change it.\n"
    "When a booking is created, rescheduled, or cancelled, the tool response includes a calendar_link and a ref.\n"
    "Always share the ref and calendar_link with the volunteer so they can add/update/remove it from their calendar.\n"
    "OVERLAPPING BOOKINGS:\n"
    "- A volunteer can only be in one place at a time. If the services they want to sign up for have overlapping start/end times, do NOT book any of them silently.\n"
    "- 'You're already signed up' overlaps are based ONLY on the MY EXISTING BOOKINGS block in the state preamble (this volunteer's own commitments). The who_signed_up array on check_availability responses shows OTHER volunteers — they are capacity info, NOT a conflict for this volunteer. Do not say 'you're already signed up' for a slot just because someone else's name appears there.\n"
    "- A conflict requires actual TIME OVERLAP between the existing booking's [start,end] and the new slot's [start,end]. Same service on the same day at NON-overlapping times is NOT a conflict — e.g. an existing 4:00-5:00 PM booking does NOT conflict with a new 12:00-2:00 PM slot, even when both are the same service. Compute the overlap arithmetically: existing_start < new_end AND existing_end > new_start. If that's false, there is NO conflict — just book.\n"
    "- When citing a conflict, the times you quote must come from the MY EXISTING BOOKINGS block verbatim. Do not invent or shift times.\n"
    "- If the volunteer asks to sign up for two or more services in one message and their times overlap, do NOT call book_appointment yet. List the services with their times, point out the overlap, and ask which one they want to book. Only call book_appointment after they pick.\n"
    "- If book_appointment returns an overlap error against an existing booking, tell the volunteer which existing booking conflicts (service name, time) and ask whether they'd like to cancel that existing booking, pick a different time, or skip the new one. Do not auto-cancel or auto-book.\n"
    "SELECTION REPLIES (your previous turn offered a list):\n"
    "- If your previous message offered a numbered or named list of services/times and the volunteer's next reply is a short selection — an ordinal (\"2\", \"the second\", \"option 1\"), an item name (\"pick n drop\", \"the food drive\"), or a clear pick (\"that one\", \"the morning slot\") — treat the reply as a FINAL selection from that list.\n"
    "- Resolve the selection to the corresponding service + time from your prior message and call book_appointment directly. Do NOT re-call check_availability or re-render the same list — the volunteer has already answered.\n"
    "- Only re-check availability if the volunteer says something that contradicts the prior list (a new date, a service that wasn't offered, an explicit \"never mind, what about X\").\n"
    "{custom_instructions}"
)

# Roster-visibility block (saved-default variant) — injected into the
# customer state preamble when the volunteer has a stored
# default_roster_visibility. Tells the LLM to OMIT share_on_roster on
# book_appointment so the saved value carries forward, and not to re-ask.
# Placeholder ({saved_display}) is filled at runtime by
# _roster_visibility_block in chat_tools.py. Edit per-tenant from the AI
# Prompts page.
CUSTOMER_ROSTER_VISIBILITY_SAVED_PROMPT = (
    "=== ROSTER VISIBILITY (already chosen) ===\n"
    "This volunteer's saved roster-visibility default is: {saved_display}.\n"
    "When you call book_appointment, OMIT the share_on_roster parameter "
    "— the tool will use this saved value automatically. DO NOT ask the "
    "volunteer how they want their name shown; that question was "
    "answered on a previous booking and the answer carries forward. The "
    "only time to re-ask is if the volunteer themselves brings it up "
    "('actually change my name to...', 'hide me from the roster', etc.) "
    "— in that case pass the new share_on_roster value and the saved "
    "default updates.\n"
    "=== END ROSTER VISIBILITY ===\n"
)

# Roster-visibility block (unset variant) — injected when there is no
# saved default. Tells the LLM to ask ONE short question and how to
# interpret the volunteer's reply so the "I see you mentioned full
# name — were you answering my earlier question?" loop can't happen.
# Placeholders ({first_name_choice}, {full_name_choice}) are filled at
# runtime — they expand to either "(Barbara)" / "(Barbara Nguyen)" or
# "(default)" / "" depending on whether we know the volunteer's name.
CUSTOMER_ROSTER_VISIBILITY_UNSET_PROMPT = (
    "=== ROSTER VISIBILITY (not yet chosen) ===\n"
    "This volunteer has no saved roster-visibility default. The system "
    "defaults to HIDDEN — they will NOT appear on the public roster "
    "until they explicitly opt in. Do NOT proactively ask how they "
    "want to appear; just call book_appointment with no share_on_roster "
    "parameter and the tool applies the hidden default.\n"
    "\n"
    "IF THE VOLUNTEER ASKS OR STATES A PREFERENCE: when their message "
    "explicitly mentions roster visibility ('show my first name', 'use "
    "my full name', 'put me on the roster', 'hide me', 'keep me "
    "private', 'people can see my name', etc.), interpret that as their "
    "choice and pass the corresponding share_on_roster=\"first_name\" / "
    "\"full_name\" / \"hidden\" on book_appointment. The tool persists "
    "the answer as their default so they aren't asked or auto-defaulted "
    "on future bookings.\n"
    "\n"
    "POST-BOOK MENTION: after a successful book_appointment call, when "
    "you read the volunteer their confirmation, you MAY briefly mention "
    "'you're hidden from the roster by default — reply \"show my first "
    "name\" any time if you'd like to appear', but only once and only "
    "when no preference has been stated.\n"
    "=== END ROSTER VISIBILITY ===\n"
)

# Post-booking confirmation hint — appended to the assistant's reply
# after book_appointment returns. Surfaces the current saved roster
# visibility so the volunteer knows what other volunteers will see AND
# how to change it. Placeholder ({roster_display}) is filled at runtime
# by handle_book_appointment with the actual stored value (first/full
# name + their real name in parens, or "hidden"). Editable per-tenant.
CUSTOMER_BOOKING_ROSTER_HINT_PROMPT = (
    "Other volunteers will see you on the roster as: {roster_display}. "
    "Reply 'change my roster to full name' / 'change my roster to first "
    "name' / 'hide me from the roster' anytime to update this — it "
    "applies to all your future bookings."
)


# Service-presentation rule — extracted from the customer system prompt
# so admins can tune the "include event when/where with each service"
# guidance per-tenant from the AI Prompts page. Substituted into the
# customer prompt at the {service_presentation} placeholder. Without this
# rule the LLM tends to list service names with no event/date/time and
# forces the volunteer to ask a follow-up question — see the list_services
# tool description for the structure of upcoming_events.
CUSTOMER_SERVICE_PRESENTATION_PROMPT = (
    "When you present services from list_services, ALWAYS include the next "
    "upcoming event for each (date, time, and location if set) — the data "
    "lives in each service's upcoming_events array. A bare list of service "
    "names with no when/where forces the volunteer to ask a second "
    "question; include the next opportunity so they can pick and sign up "
    "in one step. If a service has no upcoming_events, say so honestly "
    "('no upcoming opportunities for X yet') rather than implying they "
    "can sign up any time."
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

# Start-planning trigger rule — extracted from the admin system prompt
# so admins can tune the trigger phrases per-tenant via the AI Prompts
# UI. Injected at template-format time via the {recruitment_start}
# placeholder. The actual server-side router that backstops this rule
# lives in app/agents/recruiter/chat_tools.py
# (maybe_handle_start_campaign_directly) — see design_decisions.md #20.
RECRUITMENT_START_PROMPT = (
    "RULE 1.5 (start-planning trigger): If the admin's message indicates "
    "intent to plan / staff / fill / recruit volunteers for an event — "
    "common phrasings include 'plan for X', 'start planning for X', "
    "'recruit for X', 'recruit volunteers for X', 'campaign for X', "
    "'launch a campaign for X', 'fill X', 'staff X', 'outreach for X', "
    "'need volunteers for X' — you MUST call start_recruitment_campaign. "
    "Pass event_date (YYYY-MM-DD) and event_label if they're recoverable "
    "from the admin's message; pass nothing if not. NEVER reply with "
    "'Planning started' or similar confirmation without actually calling "
    "the tool first. If the tool returns needs_clarification:true, list "
    "the candidate events and ask which one. If it returns an error, "
    "surface it honestly."
)

# Delete-campaign trigger rule — separately editable so tenants can
# adjust trigger wording / explicit verb requirements. Substituted via
# the {recruitment_delete} placeholder. Server-side backstop lives in
# chat_tools.py (maybe_handle_delete_campaign_directly). See decision #21.
RECRUITMENT_DELETE_PROMPT = (
    "RULE 1.6 (delete-campaign trigger): If the admin EXPLICITLY says "
    "DELETE a campaign — phrasings like 'delete the X campaign', "
    "'delete campaign for X', 'delete the recruitment for X', 'delete "
    "planning for X' — you MUST call delete_recruitment_campaign. Pass "
    "campaign_id if known; otherwise pass event_date (YYYY-MM-DD) "
    "and/or event_label so the tool can resolve via the linked event. "
    "DO NOT call this tool when the admin says 'cancel' or 'pause' or "
    "'remove' — those usually mean pause outreach or cancel an EVENT, "
    "NOT delete the campaign row. If the admin's intent is ambiguous, "
    "ASK first (do not delete). If the tool returns "
    "needs_clarification:true with multiple matches, list them and ask "
    "which campaign_id to delete. NEVER reply 'deleted' without "
    "actually calling the tool first."
)

ADMIN_SYSTEM_PROMPT = (
    "CAMPAIGN VOCABULARY (read this once, apply throughout):\n"
    "The product supports — or will support — three distinct kinds of "
    "campaigns. Use the right name in every reply so admins aren't "
    "confused about which surface they're using.\n"
    "  1. MUSTER — fills an EXISTING event from the tenant's EXISTING "
    "     volunteer pool. Verbs: muster / gather / fill / staff / plan / "
    "     recruit (when scoped to an event). Synonyms admins may use: "
    "     'start a campaign for <event>', 'fill the gala', 'staff "
    "     Saturday', 'recruit for the food drive', 'mustr volunteers "
    "     for X'. This is the ONLY campaign type whose backend is "
    "     wired today (see start_recruitment_campaign tool). When you "
    "     reply, prefer 'muster' over 'campaign' for clarity.\n"
    "  2. FUNDRAISING CAMPAIGN — raises money from donors. Synonyms: "
    "     'donation campaign', 'fundraiser', 'appeal', 'donor "
    "     outreach', 'year-end appeal'. NOT YET BUILT. If the admin "
    "     asks to start one, acknowledge their intent and tell them "
    "     this surface is coming but isn't live yet. Do NOT call "
    "     start_recruitment_campaign for fundraising requests — that "
    "     tool only fills events.\n"
    "  3. RECRUITING CAMPAIGN — brings NEW volunteers into the pool "
    "     (no event yet — pure pool growth). Synonyms: 'hiring "
    "     campaign', 'volunteer drive', 'find new volunteers', "
    "     'outreach to lapsed contacts', 'sign-up drive'. NOT YET "
    "     BUILT. Same handling as fundraising: acknowledge, surface "
    "     the gap, don't mis-route.\n"
    "\n"
    "DISAMBIGUATION RULES:\n"
    "  - 'Volunteers FOR <event>' → MUSTER (call start_recruitment_campaign).\n"
    "  - 'Volunteers' with no event named AND wording implies pool "
    "    growth ('find new', 'expand the team', 'recruit new') → "
    "    RECRUITING CAMPAIGN — tell the admin this surface isn't "
    "    live; do not call start_recruitment_campaign.\n"
    "  - 'Donations', 'donors', 'raise money', 'fundraiser', 'appeal' "
    "    → FUNDRAISING CAMPAIGN; surface the gap, do not mis-route.\n"
    "  - If the admin uses 'campaign' alone with no other clue, ask "
    "    ONE short clarifying question (muster / fundraising / "
    "    recruiting?) before acting.\n"
    "\n"
    "RULE 1 (run before every other thought): If the admin's message "
    "is a MUSTER request — words like plan, fill, staff, recruit, "
    "outreach, gather, muster combined with an event reference — your "
    "FIRST AND ONLY first action is to call start_recruitment_campaign. "
    "Pass event_label and event_date if the admin mentioned them; pass "
    "nothing if they didn't. NEVER ask the admin 'when?' or 'is this a "
    "new event?' before calling this tool. NEVER call "
    "manage_specific_date_slot, check_availability, or get_schedule "
    "first. The muster tool finds the event for you and tells you when "
    "to ask for clarification. (For fundraising or recruiting "
    "campaigns, do NOT call this tool — see the vocabulary block above.)\n"
    "\n"
    "RULE 2: manage_specific_date_slot with action='add' is ONLY for "
    "creating a brand-new event when the admin literally says 'create', "
    "'add a new event', or similar. 'Plan X' is NEVER event creation.\n"
    "\n"
    "RULE 3: When start_recruitment_campaign returns "
    "needs_clarification:true with matches or upcoming_events, list "
    "them and ask the admin which one. Otherwise reply that the muster "
    "has been started.\n"
    "\n"
    "{recruitment_start}\n"
    "\n"
    "{recruitment_delete}\n"
    "\n"
    "{recruitment_approval}\n"
    "\n"
    "You are an admin assistant for {business_name}. Outside of the "
    "rules above, help the admin manage bookings, volunteers, "
    "availability, and recruitment via SMS. Be concise — this is SMS. "
    "Present data in scannable format with bullets or numbered lists.\n"
    "ROSTER RENDERING: When a tool returns a who_signed_up array, render "
    "each entry verbatim — the strings already come pre-formatted as "
    "\"Full Name (phone)\" (or just the phone when no name is on file). "
    "Do NOT prefix them with \"Phone:\", \"Volunteer:\", or similar. "
    "Do NOT strip the parenthesized phone. Admins want both fields on "
    "every signup line so two people with the same first name can be "
    "told apart.\n"
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
    "Hi{name_part}, we need {service_name} volunteers for {event_label} on "
    "{event_date} from {event_start_time} to {event_end_time} "
    "({hours}h). Reply YES to sign up or STOP to opt out."
)

# Recruitment Agent planner — runs once per campaign as a tool-use loop and
# proposes the policy + message templates + plan preview. Defined here so
# it's editable from the Admin Prompts UI alongside the SMS prompts.
RECRUITMENT_REPORTER_PROMPT = (
    "You are writing a 2–3 sentence daily SMS update for an admin who is "
    "using a volunteer recruitment agent to staff an event. Use ONLY the "
    "numbers in the payload — do not invent. Keep the entire message under "
    "300 characters so it fits in one SMS. Lead with how the event is "
    "tracking (X% filled, services short by N), mention the most recent "
    "wave activity, and finish with the next action if anything is due. "
    "Be plain and concrete; do not use emojis or marketing language."
)


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
At minimum provide a 'default' key; per-wave entries are nice-to-have. \
ALWAYS include {service_name} in every template — the volunteer needs to \
know which role they're being asked to fill so they're not surprised at \
booking time. A template that mentions only the event without the service \
leads to the volunteer signing up blind.
- plan_preview: a list of wave entries, each {wave_number, service_name, \
scheduled_at_iso, target_count, rationale}.

Be concise. Do not over-think — sensible defaults beat hedging. The admin \
can edit the plan in the UI before approval.
"""

# ── Setting keys ──

# ──────────────────────────────────────────────────────────────────────
# Event lifecycle plan prompts (decision #28; Phase 1 step 2a)
# 37 new entries registered in a single migration so the AI Prompts UI
# surfaces every template from day one. Some templates are unused
# until later phases ship — registering bulk in Phase 1 prevents
# tenant customization drift across phases.
# Variable docs live in the AI Prompts UI help text per key.
# ──────────────────────────────────────────────────────────────────────

# Volunteer-side replies (17)
PROMPT_CHECKIN_CONFIRMATION = (
    "Got it, {name} — checked in for {event_name} at {hh_mm}.\n"
    "Service: {service}\n"
    "Location: {location}\n"
    "Time: {start_time} – {end_time}\n"
    "Have a great event!"
)
PROMPT_CHECKIN_ALREADY_IN = "You're already checked in at {hh_mm} ✓."
PROMPT_CHECKIN_REENTRY_PROMPT = (
    "You checked out at {hh_mm}. Reply HERE-AGAIN (or BACK) to come back in."
)
PROMPT_CHECKIN_REENTRY_CONFIRMATION = (
    "Welcome back, {name} — re-entered at {hh_mm}. Have a great rest of the event!"
)
PROMPT_CHECKIN_DISAMBIGUATION = (
    "You're signed up for {count} events right now:\n"
    "{numbered_list}\n"
    "Reply {valid_options}."
)
PROMPT_CHECKOUT_CONFIRMATION = (
    "Thanks for showing up, {name}!\n"
    "Checked out from {event_name} at {hh_mm}.\n"
    "Service: {service}\n"
    "Total hours today: {total_hours}\n"
    "See you next time!"
)
PROMPT_SERVICE_SWITCH_PENDING = (
    "Got it, {name} — requesting to switch to {service} at {event_name}.\n"
    "Sending to admin for confirmation. We'll text you when approved."
)
PROMPT_SERVICE_ADD_PENDING = (
    "Got it, {name} — requesting to also help with {service} at {event_name}.\n"
    "Sending to admin for confirmation. We'll text you when approved."
)
PROMPT_SERVICE_UNRECOGNIZED = (
    "I didn't recognize '{service_attempted}' at {event_name}. "
    "Reply with the service name or text HELP."
)
PROMPT_WALKUP_OFFER = (
    "Hi {name}, we don't have you signed up for anything right now.\n"
    "We're running {event_name} ({start_time} – {end_time}, {location}) "
    "and have {open_spots} open spots for {service}. Want to join?\n"
    "Reply YES to walk in, NO to skip."
)
PROMPT_WALKUP_PICKER = (
    "{prompt_lead}\n"
    "{numbered_list}\n"
    "Reply {valid_options}."
)
PROMPT_WALKUP_CONFIRMATION = (
    "Welcome aboard, {name}! You're now signed up AND checked in for "
    "{event_name} at {hh_mm}.\n"
    "Service: {service}\n"
    "Location: {location}\n"
    "Time: {start_time} – {end_time}\n"
    "Thanks for jumping in — have a great event!"
)
PROMPT_NO_EVENT_FUTURE_BOOKING = (
    "Hi {name} — no event happening for you right now. "
    "Your next signup is {next_booking_description}. Reply HERE then to check in."
)
PROMPT_NO_EVENT_NO_FUTURE_BOOKING = (
    "Hi {name} — no event happening right now, and we don't have anything "
    "coming up for you. Reply EVENTS to see what's available, or we'll text "
    "you when something matches your interests."
)
PROMPT_NO_EVENT_CANCELLED = (
    "Hi {name} — looks like {cancelled_event_name} was cancelled. "
    "Sorry for the confusion! {trailing}"
)
PROMPT_LIST_EVENTS_RESPONSE = (
    "Upcoming events you can join:\n{numbered_list}\n"
    "Reply YES <number> to sign up."
)
PROMPT_LIST_BOOKINGS_RESPONSE = (
    "Your upcoming bookings:\n{numbered_list}"
)

# Admin-side replies (16)
PROMPT_ADMIN_CHECKIN_SUCCESS = (
    "✓ Checked in {volunteer_name} for {event_name} at {hh_mm}."
)
PROMPT_ADMIN_CHECKOUT_SUCCESS = (
    "✓ Checked out {volunteer_name} from {event_name} at {hh_mm}."
)
PROMPT_ADMIN_COMMAND_NAME_NOT_FOUND = (
    "'{name_attempted}' not found in {event_name}. "
    "Use the admin UI to add them first."
)
PROMPT_ADMIN_COMMAND_USAGE_HELP = (
    "Usage:\n"
    "  CHECKIN <name> — check in a volunteer\n"
    "  CHECKIN ME — check yourself in (if you have a personal Booking)\n"
    "  CHECKOUT <name> / CHECKOUT ME — analogous for checkout\n"
    "  STATUS [<event>] — roster summary\n"
    "  RESERVE [<event>] [| <service>] — reserve yourself for an event\n"
    "  APPROVE <name> / REJECT <name> — dispose of pending service-log entries\n"
    "  STOP STATUS / STOP STATUS ALL — silence pings\n"
    "  CANCEL — clear active picker/disambiguation"
)
PROMPT_ADMIN_COMMAND_DISAMBIGUATION = (
    "Multiple volunteers match '{name_attempted}':\n"
    "{numbered_list}\n"
    "Reply {valid_options}."
)
PROMPT_ADMIN_SUPER_ADMIN_REJECTION = (
    "SMS admin commands require a tenant-scoped admin. Use the dashboard at {admin_panel_url}."
)
PROMPT_ADMIN_RESERVE_EVENT_PICKER = (
    "Pick an event to reserve for:\n"
    "{numbered_list}\n"
    "Reply {valid_options}. Or send the event name."
)
PROMPT_ADMIN_RESERVE_SERVICE_PICKER = (
    "Pick a service for {event_name}:\n"
    "{numbered_list}\n"
    "Reply {valid_options}."
)
PROMPT_ADMIN_RESERVE_CONFIRMATION = (
    "Reserved you for {event_name} — {service} ({start_time}, {location}).\n"
    "Reply CHECKIN ME when you arrive to check yourself in."
)
PROMPT_ADMIN_RESERVE_NO_CAPACITY = (
    "Sorry — {event_name} is full and no other events have open capacity right now. "
    "Try RESERVE again later when something opens up."
)
PROMPT_ADMIN_RESERVE_SLOT_FILLED = (
    "Sorry — the {filled_service} spot at {event_name} just filled up while "
    "you were deciding. Other open services for that event:\n"
    "{numbered_list}\n"
    "Reply {valid_options}, or text CANCEL to skip, or text RESERVE to start over."
)
PROMPT_ADMIN_SERVICE_APPROVAL_REQUEST = (
    "{volunteer_name} at {event_name}: wants to switch from {from_service} to "
    "{to_service}. Approve: {link}. Reply YES to approve, NO to reject."
)
PROMPT_ADMIN_SERVICE_APPROVAL_DONE = "Done."
PROMPT_ADMIN_WALKUP_CANDIDATE_NOTIFICATION = (
    "Unknown phone ({phone}) texted HERE during {event_name}. "
    "Invite or dismiss? {link}"
)
PROMPT_ADMIN_LIVE_EVENTS_CONTEXT_BLOCK = (
    "Currently live events at this tenant:\n"
    "{event_list}\n"
    "If the admin asks anything related to status, current activity, or "
    "\"what's going on,\" offer a status summary using these."
)
PROMPT_ADMIN_PERSONAL_BOOKINGS_CONTEXT_BLOCK = (
    "Your personal bookings:\n"
    "{personal_booking_list}\n"
    "If the admin asks about their own bookings (e.g., \"am I checked in?\", "
    "\"what's my next shift?\"), answer using these."
)

# Scheduler / status pings (3)
PROMPT_ROSTER_STATUS_PING = (
    "{event_name}: {checked_in_count}/{total_count} checked in. "
    "Missing: {missing_names_capped}. {link}"
)
PROMPT_ROSTER_STATUS_ALL_IN = "{event_name}: all checked in ✓"
PROMPT_POST_EVENT_REVIEW_AVAILABLE = (
    "{event_name} ended. {pending_review_count} reviews waiting. {link}"
)

# Recognition (1)
PROMPT_RECOGNITION_CONGRATULATIONS = (
    "Congrats, {volunteer_name}! You just earned the {award_label} milestone. "
    "{award_description}"
)


PROMPT_KEYS = {
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
    "prompt_recruitment_start": RECRUITMENT_START_PROMPT,
    "prompt_recruitment_delete": RECRUITMENT_DELETE_PROMPT,
    "prompt_customer_service_presentation": CUSTOMER_SERVICE_PRESENTATION_PROMPT,
    "prompt_recruitment_reporter": RECRUITMENT_REPORTER_PROMPT,
    "prompt_customer_roster_saved": CUSTOMER_ROSTER_VISIBILITY_SAVED_PROMPT,
    "prompt_customer_roster_unset": CUSTOMER_ROSTER_VISIBILITY_UNSET_PROMPT,
    "prompt_customer_booking_roster_hint": CUSTOMER_BOOKING_ROSTER_HINT_PROMPT,
    # ── Event lifecycle plan (37 new entries — Phase 1 step 2a) ──
    # Volunteer-side replies (17)
    "prompt_checkin_confirmation": PROMPT_CHECKIN_CONFIRMATION,
    "prompt_checkin_already_in": PROMPT_CHECKIN_ALREADY_IN,
    "prompt_checkin_reentry_prompt": PROMPT_CHECKIN_REENTRY_PROMPT,
    "prompt_checkin_reentry_confirmation": PROMPT_CHECKIN_REENTRY_CONFIRMATION,
    "prompt_checkin_disambiguation": PROMPT_CHECKIN_DISAMBIGUATION,
    "prompt_checkout_confirmation": PROMPT_CHECKOUT_CONFIRMATION,
    "prompt_service_switch_pending": PROMPT_SERVICE_SWITCH_PENDING,
    "prompt_service_add_pending": PROMPT_SERVICE_ADD_PENDING,
    "prompt_service_unrecognized": PROMPT_SERVICE_UNRECOGNIZED,
    "prompt_walkup_offer": PROMPT_WALKUP_OFFER,
    "prompt_walkup_picker": PROMPT_WALKUP_PICKER,
    "prompt_walkup_confirmation": PROMPT_WALKUP_CONFIRMATION,
    "prompt_no_event_future_booking": PROMPT_NO_EVENT_FUTURE_BOOKING,
    "prompt_no_event_no_future_booking": PROMPT_NO_EVENT_NO_FUTURE_BOOKING,
    "prompt_no_event_cancelled": PROMPT_NO_EVENT_CANCELLED,
    "prompt_list_events_response": PROMPT_LIST_EVENTS_RESPONSE,
    "prompt_list_bookings_response": PROMPT_LIST_BOOKINGS_RESPONSE,
    # Admin-side replies (16)
    "prompt_admin_checkin_success": PROMPT_ADMIN_CHECKIN_SUCCESS,
    "prompt_admin_checkout_success": PROMPT_ADMIN_CHECKOUT_SUCCESS,
    "prompt_admin_command_name_not_found": PROMPT_ADMIN_COMMAND_NAME_NOT_FOUND,
    "prompt_admin_command_usage_help": PROMPT_ADMIN_COMMAND_USAGE_HELP,
    "prompt_admin_command_disambiguation": PROMPT_ADMIN_COMMAND_DISAMBIGUATION,
    "prompt_admin_super_admin_rejection": PROMPT_ADMIN_SUPER_ADMIN_REJECTION,
    "prompt_admin_reserve_event_picker": PROMPT_ADMIN_RESERVE_EVENT_PICKER,
    "prompt_admin_reserve_service_picker": PROMPT_ADMIN_RESERVE_SERVICE_PICKER,
    "prompt_admin_reserve_confirmation": PROMPT_ADMIN_RESERVE_CONFIRMATION,
    "prompt_admin_reserve_no_capacity": PROMPT_ADMIN_RESERVE_NO_CAPACITY,
    "prompt_admin_reserve_slot_filled": PROMPT_ADMIN_RESERVE_SLOT_FILLED,
    "prompt_admin_service_approval_request": PROMPT_ADMIN_SERVICE_APPROVAL_REQUEST,
    "prompt_admin_service_approval_done": PROMPT_ADMIN_SERVICE_APPROVAL_DONE,
    "prompt_admin_walkup_candidate_notification": PROMPT_ADMIN_WALKUP_CANDIDATE_NOTIFICATION,
    "prompt_admin_live_events_context_block": PROMPT_ADMIN_LIVE_EVENTS_CONTEXT_BLOCK,
    "prompt_admin_personal_bookings_context_block": PROMPT_ADMIN_PERSONAL_BOOKINGS_CONTEXT_BLOCK,
    # Scheduler / status pings (3)
    "prompt_roster_status_ping": PROMPT_ROSTER_STATUS_PING,
    "prompt_roster_status_all_in": PROMPT_ROSTER_STATUS_ALL_IN,
    "prompt_post_event_review_available": PROMPT_POST_EVENT_REVIEW_AVAILABLE,
    # Recognition (1)
    "prompt_recognition_congratulations": PROMPT_RECOGNITION_CONGRATULATIONS,
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


async def get_customer_system_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """Return the customer system prompt with the service-presentation rule
    substituted in from its own (separately editable) prompt entry.

    Substitution uses .replace (not .format) so the injected rule body
    can contain its own braces without crashing the outer .format() call
    that fills {business_name} / {custom_instructions} downstream.
    """
    raw = await _get_prompt(
        db, "prompt_customer_system", CUSTOMER_SYSTEM_PROMPT, tenant_id
    )
    if "{service_presentation}" in raw:
        rule = await _get_prompt(
            db,
            "prompt_customer_service_presentation",
            CUSTOMER_SERVICE_PRESENTATION_PROMPT,
            tenant_id,
        )
        raw = raw.replace("{service_presentation}", rule)
    return raw


async def get_admin_system_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """Return the admin system prompt with the recruitment-approval and
    recruitment-start rules substituted in from their own (separately
    editable) prompt entries.

    Substitution uses .replace (not .format) so the injected rule
    bodies can themselves contain {business_name} or other placeholders
    without crashing the outer .format() call.
    """
    raw = await _get_prompt(
        db, "prompt_admin_system", ADMIN_SYSTEM_PROMPT, tenant_id
    )
    if "{recruitment_start}" in raw:
        start = await _get_prompt(
            db,
            "prompt_recruitment_start",
            RECRUITMENT_START_PROMPT,
            tenant_id,
        )
        raw = raw.replace("{recruitment_start}", start)
    if "{recruitment_delete}" in raw:
        delete_rule = await _get_prompt(
            db,
            "prompt_recruitment_delete",
            RECRUITMENT_DELETE_PROMPT,
            tenant_id,
        )
        raw = raw.replace("{recruitment_delete}", delete_rule)
    if "{recruitment_approval}" in raw:
        approval = await _get_prompt(
            db,
            "prompt_recruitment_approval",
            RECRUITMENT_APPROVAL_PROMPT,
            tenant_id,
        )
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


async def get_recruitment_reporter_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """System prompt for the Recruitment Agent's daily-report narrative.

    Drives the 2-3 sentence SMS the agent texts admins each day with
    fill-rate progress + wave activity + next action. Per-tenant
    editable via the AI Prompts page so admins can tune tone, length,
    what to lead with, whether to allow emojis, etc.
    """
    return await _get_prompt(
        db, "prompt_recruitment_reporter", RECRUITMENT_REPORTER_PROMPT, tenant_id
    )


async def get_customer_roster_saved_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """Preamble block injected when a volunteer HAS a saved roster default."""
    return await _get_prompt(
        db,
        "prompt_customer_roster_saved",
        CUSTOMER_ROSTER_VISIBILITY_SAVED_PROMPT,
        tenant_id,
    )


async def get_customer_roster_unset_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """Preamble block injected when a volunteer has NO saved roster default."""
    return await _get_prompt(
        db,
        "prompt_customer_roster_unset",
        CUSTOMER_ROSTER_VISIBILITY_UNSET_PROMPT,
        tenant_id,
    )


async def get_customer_booking_roster_hint_prompt(
    db: AsyncSession, tenant_id: uuid.UUID | None = None,
) -> str:
    """One-line hint surfaced in book_appointment's success response so the
    assistant can tell the volunteer how they appear on the roster + how to
    change it. Editable per-tenant from the AI Prompts page.
    """
    return await _get_prompt(
        db,
        "prompt_customer_booking_roster_hint",
        CUSTOMER_BOOKING_ROSTER_HINT_PROMPT,
        tenant_id,
    )
