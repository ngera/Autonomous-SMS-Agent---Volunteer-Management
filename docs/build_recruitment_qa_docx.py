"""Generate recruitment_agent_qa.docx from the project Q&A.

Run: python docs/build_recruitment_qa_docx.py
Output: docs/recruitment_agent_qa.docx
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

# Each entry: (question, answer)
# Answer may contain "\n" for paragraph breaks and "- " prefix for bullets.
QA: list[tuple[str, str]] = [
    (
        "What industry is your business in? (e.g. Financial services, Healthcare, Education, etc.)",
        "Volunteer / community-operations SaaS — adjacent to nonprofit tech, faith-based community management, and event-staffing platforms. The schema vocabulary (volunteers, events, service_config, opt-in consent, no-show suspensions, free price_at_booking) indicates this is not paid-appointment territory like beauty / medical; it's running shifts for unpaid contributors.",
    ),
    (
        "What are the key challenges (headwinds) and opportunities (tailwinds) impacting growth in your industry? Who are the key competitors?",
        "Headwinds:\n"
        "- Volunteer fatigue — declining response rates to outreach.\n"
        "- SMS deliverability / compliance tightening (10DLC, A2P 10DLC fees, STOP rules).\n"
        "- Competition from cheaper general tools (SignUp Genius, Google Forms + Slack) that nonprofits use for free.\n"
        "- Recession-sensitive budgets — nonprofits cut software first.\n\n"
        "Tailwinds:\n"
        "- AI lowers the operations cost enough that very small orgs (1 staff coordinator) can run formal volunteer programs.\n"
        "- Mobile-first volunteers prefer SMS over email / portal logins.\n"
        "- Compliance complexity (consent, GDPR-style records) favors managed platforms over DIY spreadsheets.\n\n"
        "Competitors: SignUpGenius, VolunteerLocal, Better Impact, Galaxy Digital, Bloomerang Volunteer (formerly Volgistics), Givelify-Volunteer, plus the long tail of WhatsApp groups + spreadsheets.",
    ),
    (
        "What is the projected growth rate of your target market segment over the next 3–5 years?",
        "Volunteer-management software is a small slice (~$0.3–0.5B globally) growing roughly 8–11% CAGR through 2028 — driven by post-pandemic re-engagement and digitization of mid-size nonprofits. (Estimate, not a researched figure.)",
    ),
    (
        "What growth stage is your business currently in (e.g., startup, scale-up, mature)?",
        "Early / startup. Single-product, evolving schema (still adding migrations such as a025), no productionized billing infrastructure observed, multi-tenant just shipped.",
    ),
    (
        "How does your business make money? What do they sell? What is your primary revenue model (e.g., subscription, freemium, licensing, marketplace, transactional)?",
        "Inferred from the multi-tenant Tenant model (per-tenant credentials, slug, business_name): SaaS subscription per tenant, likely tiered by volunteer count or event volume. Pass-through Twilio / Anthropic costs may be billed at margin or absorbed.",
    ),
    (
        "Who is your primary customer base (B2B, B2C, B2B2C)?",
        "B2B2C. The org (tenant) buys; admins are the day-to-day buyers / users; volunteers are the end-users who actually receive SMS.",
    ),
    (
        "What are the key differentiators for your company?",
        "- SMS-first — no volunteer app or login required.\n"
        "- Multi-tenant from the ground up — per-tenant Twilio number, AI API key, prompts.\n"
        "- AI conversational booking out of the box (existing tool_use pipeline).\n"
        "- Now: the Recruitment Agent — proactively fills events instead of just recording signups.",
    ),
    (
        "Who are the customers (buyers) of your product?",
        "Volunteer coordinators / operations directors at community orgs, faith communities, food banks, and festival / event orgs. Typical buyer: 1–3 person admin team running 5–50 events / month.",
    ),
    (
        "Who are the end-users of your product? Which users are the most revenue-generating / revenue-impacting? What are their goals, roles, and context?",
        "- Admin / Manager (paying user) — uses the dashboard daily; revenue is bound to their retention. Highest revenue impact.\n"
        "- Volunteer (free user) — receives SMS, books via SMS, never logs in. No direct revenue but their satisfaction → retention → admin retention.",
    ),
    (
        "Product-led: What are the core features of your product, and how do they address user needs?",
        "1. SMS conversational booking (Claude Haiku tool-use).\n"
        "2. Admin chat tools (same SMS pipeline, admin-only tool set — manage services, schedule, suspensions).\n"
        "3. Calendar of events + recurring availability with per-service min / max volunteers.\n"
        "4. Consent management, strikes, suspensions, opt-in flow.\n"
        "5. Reminders + follow-ups (pattern-based daily jobs).\n"
        "6. Announcements with audience targeting.\n"
        "7. New: Recruitment Agent — proactive volunteer-filling layer.\n"
        "8. Analytics, token-usage dashboard, multi-volunteer SMS test tool.",
    ),
    (
        "Who is your AI product / feature for? (Internal users, external users, an influencer, a buyer, etc.)",
        "Admins (paying users / influencers internal to the org). Volunteers are touched indirectly via the SMS the agent sends, but the user driving the AI is the admin.",
    ),
    (
        "What is the typical journey for your target persona when they are using your product / service, focusing on their ideal experience (happy path)?",
        "1. Admin creates an event in the calendar with service_config (e.g., 3 cooks, 5 servers).\n"
        "2. Admin clicks 'Recruit volunteers' on the event page (or texts 'plan recruitment for sat may 17').\n"
        "3. ~60 seconds later, admin receives a follow-up SMS: 'Plan ready: 3 waves over 14 days, targeting 12 experienced cooks and 8 servers. Reply APPROVE…'\n"
        "4. Admin replies 'approve' (or clicks Approve in dashboard).\n"
        "5. Agent runs autonomously: fires SMS waves on schedule, ranks eligible volunteers, respects consent / cooldowns.\n"
        "6. Every morning at 08:15, admin gets a 1-SMS status update: 'BBQ May 17: 78% filled (cooks 3/3, servers 5/8). 12 contacted yesterday, 2 new signups. Next wave in 6 hrs.'\n"
        "7. If pool exhausted or service can't fill, agent pauses and SMSes the admin.",
    ),
    (
        "Where does the user experience friction, obstacles, or unmet needs throughout the journey? Which pain-points are most frequent and severe?",
        "Severe + frequent:\n"
        "- Admin manually drafts each announcement and decides who to send to → time sink, error-prone (announces a service to volunteers not configured for it).\n"
        "- Admin has no way to know if 5 waves of outreach are needed vs. 1, when to send them, or who's 'best' for a service.\n\n"
        "Frequent:\n"
        "- Spamming the same volunteer across overlapping events.\n\n"
        "Moderate:\n"
        "- No visibility into how many events are at risk of not being staffed.\n"
        "- Reactive — admin only finds out an event won't fill the day before.",
    ),
    (
        "From your list of pain points, identify those that can effectively be addressed using Generative AI. Rank with the most severe and frequently occurring first.",
        "1. Plan generation — what waves, when, who, what to say. Pure planning task with rich structured inputs. Highest impact, fits LLM strength.\n"
        "2. Daily narrative reports — turning numeric snapshots into 1-SMS summaries the admin can absorb without opening the app.\n"
        "3. Adaptive copywriting — per-wave message templates that adjust tone as event approaches ('3 days left, last call…').\n"
        "4. Lower priority for AI: recipient targeting + scoring + cooldown enforcement — better as deterministic code (which is what was built).",
    ),
    (
        "Ideate potential solutions to address your AI-solvable pain points. Focus on quantity over quality.",
        "- Autonomous recruitment agent (chosen).\n"
        "- 'Suggest who to message' advisory mode admin still drives.\n"
        "- AI-written event description from a 1-line prompt.\n"
        "- Auto-summarize an admin's day in one SMS.\n"
        "- Predict no-shows.\n"
        "- Auto-draft event-specific reminders.\n"
        "- Detect 'at risk' events and surface to dashboard.\n"
        "- Sentiment analysis on volunteer replies.\n"
        "- Auto-resolve admin SMS questions ('how many cooks for sat?').",
    ),
    (
        "Rank your ideated solutions based on impact and feasibility. Identify your top three AI solutions, and clearly select the one you'll focus on.",
        "Top 3 (impact × feasibility):\n"
        "1. Recruitment Agent ← chosen.\n"
        "2. At-risk event detector (cheap, deterministic).\n"
        "3. AI-drafted reminders.\n\n"
        "Why the Recruitment Agent: highest leverage. Addresses the most-frequent admin task; the data is already in the schema; the LLM is asked to do something it's good at (planning + brief narrative) while the deterministic state machine handles the parts LLMs do badly (filtering, cooldowns, ranking).",
    ),
    (
        "Assuming your product or feature works as desired, what is the target state workflow?",
        "Sidebar → Recruitment → Campaigns list (aggregate stats + sortable table). Click campaign → detail page (plan summary, wave timeline, fill bars, recent reports). Pre-approval state: editable message templates + Regenerate / Approve buttons. Active state: pause / cancel / cancel-wave actions. Event detail → 'Recruit volunteers' CTA jumps straight to a new campaign. Admin only intervenes at approval gate and on escalation; everything else is automatic.",
    ),
    (
        "How will users navigate through your AI solution? What are the key steps and decision points? What information will be displayed at each stage? What specific UI elements are needed on each screen? How will the layout accommodate AI features?",
        "Navigation: Sidebar 'Recruitment' link → list page → detail page. Decision points: Approve / Regenerate / Edit templates / Pause / Cancel / Cancel-wave.\n\n"
        "List page: aggregate stats strip (5 cards: active, needed, signed-up, messaged 7d, at-risk), filter (status select + at-risk toggle), table with columns event, date, days, status badge, fill bars, last/next wave, at-risk callout. Default sort by event date ASC.\n\n"
        "Detail page: plan_summary text block + plan_preview wave list + editable Textarea templates with token reference + waves Table + recent daily reports list. Status-aware action buttons.",
    ),
    (
        "What aspects of the AI solution will you demonstrate in your prototype? How will the AI inputs, processing, and outputs be presented visually? Which features are essential for launch? What can be left for later?",
        "Demo:\n"
        "- Input: admin clicks one button on an event OR texts one sentence.\n"
        "- Processing: planner tool-use loop visible in token-usage dashboard; deterministic tick loop drives waves; daily reporter LLM produces narrative.\n"
        "- Output: SMS to admin (planned and visible in test-conversation), SMS to volunteers (visible in multi-volunteer test panel), persisted plan + wave timeline in dashboard.\n\n"
        "Essential for launch: planner, approval, tick, daily report, attribution.\n"
        "Later: response-rate-aware adaptive replanning, AI-suggested template rewrites, predictive at-risk scoring.",
    ),
    (
        "Create an initial master prompt. Consider tone, structure, system instruction, examples, output format.",
        "Already in code: app/agents/recruiter/planner.py::PLANNER_SYSTEM_PROMPT and app/agents/recruiter/reporter.py::REPORTER_SYSTEM_PROMPT.\n\n"
        "Tone: plain, operational, no marketing language, no emojis, terse.\n"
        "Structure: system prompt sets role + tool sequence + output constraints; user message is minimal seed; LLM gathers facts via tools then emits final text.\n"
        "System rules (planner): must call get_event_details first; must call propose_plan exactly once; final assistant text becomes the SMS (≤300 chars); no clarifying questions.\n"
        "System rules (reporter): use ONLY numbers in payload, no inventions; ≤300 chars; lead with fill %, mention recent activity, end with next action.\n"
        "Tenant override: SystemSetting(key='recruitment_agent_prompt').",
    ),
    (
        "What specific quality benchmarks (e.g., clarity, relevance, tone, accuracy, hallucination avoidance) will define 'good' output?",
        "- Planner narrative SMS: ≤300 chars; mentions services + total volunteers needed + when first wave fires; no hallucinated services or dates; structured propose_plan call has all required fields.\n"
        "- Reporter SMS: ≤300 chars; numbers match payload exactly; lead with fill %; ends with next action or 'no action needed.'\n"
        "- Plan preview JSON: every wave has wave_number, service_name, scheduled_at_iso, target_count, rationale; scheduled_at_iso never in the past.\n"
        "- Targeting (deterministic, not LLM): no consent violations, no service-eligibility violations, cooldowns honored — covered by unit tests.",
    ),
    (
        "What specific example use cases, edge cases, and negative cases should be covered by test prompts and outputs?",
        "Happy: event in 14 days, 2 services, healthy eligible pool.\n"
        "Edge: event in 2 days (offsets in past must snap to now).\n"
        "Edge: only 1 service needed.\n"
        "Edge: response_rates data missing (cold tenant).\n"
        "Negative: LLM emits no propose_plan call → planner marks campaign FAILED, sends error SMS.\n"
        "Negative: LLM emits malformed policy → sanity floors in _h_propose_plan clamp values.\n"
        "Negative: Anthropic API 5xx → fallback deterministic narrative in reporter.",
    ),
    (
        "Which AI model is best suited for your solution and why? What capabilities and limitations does it have? How will it integrate with your product?",
        "Model: Claude Haiku 4.5 (claude-haiku-4-5-20251001). Reasons: cheap, fast, supports tool-use; the planning task is well-scoped (not a deep reasoning task). Per-tenant override via SystemSetting(key='ai_model') already exists.\n\n"
        "Capabilities used: tool-use multi-round (planner), single-shot completion (reporter).\n"
        "Limitations: 200K context (plenty); can hallucinate when numbers are passed as freeform text → mitigated by passing structured JSON payload + system rule 'use ONLY numbers in payload.'\n"
        "Integration: existing run_tool_conversation loop (app/modules/tool_executor.py) with new handlers injection point; tenant credentials from Tenant.anthropic_api_key.",
    ),
    (
        "What are the required input fields for the AI? Indicate format, source, requirement.",
        "Required:\n"
        "- Campaign create: event_slot_id (UUID, from existing event).\n"
        "- Implicit (resolved by planner tools): event date / time / location / services / current signups (from DB), eligible candidate pool (from targeting.select_recipients), recent response rate (from existing Announcement + Booking tables).",
    ),
    (
        "Are there any optional or user-customizable fields? How do they impact the AI's output?",
        "- goals[] — admin can override targets per service (default: slot's min_required).\n"
        "- service_name filter (chat tool only) — limit campaign to one service.\n"
        "- target_per_service (chat tool only) — override target.\n"
        "- Per-tenant recruitment_agent_prompt SystemSetting override.\n"
        "- Admin can PATCH message_templates or policy.wave_offsets_days pre-approval.",
    ),
    (
        "What criteria will you use to judge output as 'good'? (e.g., structure, use of keywords, tone, factuality, relevance)",
        "Structural (script-checkable): all required JSON fields present, numbers within bounds, no past timestamps.\n"
        "Behavioral (script-checkable): unit tests on targeting + scheduler_engine (33 passing).\n"
        "Qualitative (human): admin reads SMS and understands status without opening app.",
    ),
    (
        "Are there any criteria that require human judgment or qualitative assessment?",
        "Yes — narrative readability and prioritization sense (does the SMS actually answer 'is this event going to be filled?'). The numeric correctness checks can be automated, but tone calibration is human-graded for the first ~50 reports per tenant.",
    ),
    (
        "What is your starting system prompt for the model? What variations will you test? What techniques will you use to optimize performance? List initial instructions, persona, inputs, and constraints.",
        "Starting prompts in code: PLANNER_SYSTEM_PROMPT and REPORTER_SYSTEM_PROMPT.\n\n"
        "Persona: 'planning brain of a Volunteer Recruitment Agent' / 'writing a 2–3 sentence daily SMS update for an admin.'\n"
        "Inputs: structured JSON payload (planner gets access via tools; reporter gets the dict).\n"
        "Constraints: must call propose_plan exactly once (planner); use ONLY numbers in payload (reporter); ≤300 chars output.\n\n"
        "Variations to test: with / without overshoot guidance; with / without 'be concise' framing; with / without per-tenant tone override.\n"
        "Optimization: tool-use to ground in real data; tightly scoped output; deterministic fallback for reporter on API failure.",
    ),
    (
        "If revised, what changes did you make and why? How do you track and record prompt evolution?",
        "Initial prompt as shipped. Future revisions tracked via git history on planner.py / reporter.py + per-tenant SystemSetting(key='recruitment_agent_prompt') overrides. Recommend keeping a CHANGELOG.md entry per prompt change with the failure case that motivated it.",
    ),
    (
        "What data sources will you use? How will you prepare data for model training or evaluation? For RAG: how will you chunk, embed, retrieve relevant information?",
        "Sources: tenant's PostgreSQL — appointment_types, contacts, contact_consent, contact_preferred_types, bookings, announcements, specific_date_slots, recruitment_waves.\n"
        "Preparation: aggregated into typed JSON payloads at tool-call time (no chunking / embedding needed — direct SQL).\n"
        "No RAG required for v1; data volume per call is small (event details + top-N candidates + response-rate stat).",
    ),
    (
        "What are the most common inputs and expected outputs? Use real data if possible.",
        "Common input: event_slot_id for an event 7–14 days out with 1–3 services, each needing 3–8 volunteers.\n"
        "Expected output: structured plan with wave_offsets_days like [14, 7, 3, 1] (skipping past offsets), per-wave SMS templates using {first_name} + {event_label} tokens, plan_summary like 'BBQ May 17 plan: 3 cooks + 8 servers needed, 4 waves starting today targeting experienced volunteers first.'",
    ),
    (
        "What examples test the AI's limits? (e.g., missing data, ambiguous input, out-of-domain)",
        "- Cold tenant with no booking history → response-rate tool returns null → planner must still propose a plan with default overshoot.\n"
        "- Event in 1 day → wave_offsets must collapse to a single immediate wave.\n"
        "- Service with zero eligible volunteers → planner should flag this in plan_summary, not silently propose an empty wave.\n"
        "- Multi-service event where one service is over-eligible and another under-eligible.",
    ),
    (
        "Run your input data with the prompt. How did your output perform in manual review? Which examples failed which criteria, and why?",
        "TBD — to be done in pilot. Current verification: 33 deterministic unit tests pass (targeting + scheduler_engine + eligibility); LLM-output review requires live tenants. Plan to capture first 20 planner runs + first 50 reporter runs in pilot for qualitative review.",
    ),
    (
        "What pass/fail rate or scores did the AI achieve on core criteria?",
        "Pre-pilot. Target: planner success rate (campaigns reaching awaiting_approval) ≥95%; reporter fallback rate <10%; zero consent violations (deterministic — should be 100%).",
    ),
    (
        "What edge cases did you identify in testing or real usage?",
        "From scaffolding tests:\n"
        "- Already-filled service when wave fires → executor marks SKIPPED.\n"
        "- Event date passed → ABANDON action.\n"
        "- No eligible recipients after filters → ESCALATE + admin SMS.\n"
        "- Late opt-in between approval and send → captured because targeting resolves at send time, not approval.\n"
        "- Two campaigns targeting same multi-skill volunteer → 24h global per-contact cap prevents bombardment.",
    ),
    (
        "What prompt or system adjustments have you made based on failures, feedback, or edge case observations?",
        "Built-in safeguards already in place:\n"
        "- Sanity floor on overshoot_factor (clamp 1.0–3.0) in propose_plan handler.\n"
        "- Deterministic narrative fallback in reporter on Anthropic API failure.\n"
        "- Hard 'must call propose_plan' rule in planner system prompt to prevent silent no-op.\n"
        "Future adjustments will be driven by pilot feedback.",
    ),
    (
        "What is your chosen approach for evaluation (human, model grader, script)? How will you scale testing to diverse / large test sets?",
        "Hybrid:\n"
        "- Script: structural validation of propose_plan output; numeric checks on reporter (numbers in narrative match payload).\n"
        "- LLM-as-judge: cheap rubric scoring of narrative clarity for batch evals.\n"
        "- Human: spot-check 5% of pilot output for tone calibration.\n"
        "Scaling: golden-set of 10–20 planning scenarios + nightly run on each; growing as pilot reveals new scenarios.",
    ),
    (
        "How often will you re-run evaluations for new data, new prompts, or post-launch monitoring?",
        "- On every prompt edit (CI gate).\n"
        "- On every model version bump.\n"
        "- Monthly regression on the golden-set as routine sanity check.\n"
        "- Per-tenant: weekly aggregate of planner success rate + reporter fallback rate.",
    ),
    (
        "Is infra (APIs, databases, rate limits, monitoring, rollback) tested and documented?",
        "- Rate limiting: existing setup_rate_limiting (slowapi) covers the API; recommend adding a per-tenant cap on POST /campaigns to prevent planner-spam.\n"
        "- Monitoring: token-usage dashboard records per-call; structured logs via get_logger('recruiter.*').\n"
        "- Rollback: status enum supports cancelled + paused; admin can stop any campaign at any time; waves can be cancelled per-row.\n"
        "- Migrations: idempotent (CREATE TABLE IF NOT EXISTS, DO $$ … EXCEPTION WHEN duplicate_object).",
    ),
    (
        "Have internal teams (support, comms, legal) been trained? Is documentation complete?",
        "TBD pre-launch. Pre-launch checklist: (a) one-page operator doc covering planner failure modes + how to manually pause a campaign, (b) consent / opt-out training reminder for support — agent inherits existing STOP keyword handling, (c) legal review of: data sent to Anthropic API (currently event metadata + scored candidate IDs/names — no phone numbers).",
    ),
    (
        "What is your launch approach? Pilot, A/B test, or all users — who gets access and when?",
        "Pilot with 2–3 friendly tenants → 2-week soak → enable for all on a per-tenant feature flag (suggested: new SystemSetting(key='recruitment_agent_enabled')).",
    ),
    (
        "How will you ensure readiness for scale? How will you monitor initial volume and scale up?",
        "- Per-tenant feature flag means rollout is incremental.\n"
        "- Token-usage dashboard surfaces LLM cost per tenant; cap via per-tenant max-campaigns-per-week if needed.\n"
        "- recruitment_tick is async + per-tenant isolated; one bad tenant can't block others.\n"
        "- Monitor: planner success rate, reporter delivery rate, average waves-per-campaign, average SMS-per-campaign — alert if any spike 2x baseline.",
    ),
    (
        "What assets (FAQ, demo, guides) will you prepare for external communication / marketing?",
        "- A one-page 'How the Recruitment Agent works' doc.\n"
        "- A 90-second screen-recording demo (event → CTA → SMS → approve → first wave fires).\n"
        "- Short FAQ covering: 'Will it message volunteers I haven't approved?' (no), 'Can I edit the messages?' (yes pre-approval), 'What if it doesn't fill the event?' (escalates to you).",
    ),
    (
        "How will you communicate launch plans, progress, and outcomes internally?",
        "- In-product changelog entry for tenants.\n"
        "- Weekly async update during pilot (campaigns created, fill rate, escalation rate).\n"
        "- Post-launch retro at 30 days.",
    ),
    (
        "How do you handle and protect user data, including storage, privacy, and compliance?",
        "- Volunteer phone numbers + consent state already PII handled by existing schema; recruitment adds no new PII categories.\n"
        "- All SMS routes through existing Twilio path → STOP keyword handling inherited.\n"
        "- Per-tenant credentials means PII does not cross tenant boundaries.\n"
        "- Anthropic API call sends event metadata + contact scores. Verify (and possibly redact) names sent in get_ranked_candidates output before launch.",
    ),
    (
        "Are content moderation, legal, and audit processes in place? Are you compliant with regulations needed for your domain?",
        "- Existing screener + abuse detection handles inbound; outbound is template-based + admin-approved per campaign.\n"
        "- Audit: every wave creates a recruitment_waves row with targeted_contact_ids snapshot + linked Announcement; every fired SMS is in conversation history.\n"
        "- Compliance: SMS opt-in / opt-out + STOP handling is in place; recruitment respects existing ContactConsent gates as hard filters in targeting.\n"
        "- Legal review needed pre-launch for: terms-of-service language about AI-driven outreach.",
    ),
    (
        "What user metrics will indicate success? What business metrics will demonstrate value?",
        "User metrics:\n"
        "- % of events that hit min_required by event date.\n"
        "- Admin time-to-staff-event (campaign create → fully filled).\n"
        "- Daily report delivery rate (proxy for usefulness).\n"
        "- Admin retention of recruitment feature (campaigns created per admin per month).\n\n"
        "Business metrics:\n"
        "- Tenant retention delta for tenants using vs. not using recruitment.\n"
        "- Per-campaign LLM cost (existing token_usage_router gives per-source breakdown).\n"
        "- Volunteer opt-out rate during active campaigns (should not spike vs. baseline).",
    ),
    (
        "How will you measure AI performance and accuracy?",
        "- Planner success rate (campaigns reaching awaiting_approval / campaigns created).\n"
        "- Fallback rate (reporter narrative falls back to deterministic).\n"
        "- Wave-skip rate (waves where targeting returned empty).\n"
        "- Per-campaign attribution rate (signups attributed / signups in event).\n"
        "- Human spot-check on first 50 reports per tenant for tone / accuracy.",
    ),
    (
        "Where can users get support? Is escalation and ownership clear?",
        "- Admins can ask the existing AI assistant via SMS ('recruitment status').\n"
        "- For bugs / issues: support ticket through existing channel.\n"
        "- Agent escalates to admin automatically (paused + SMS) when stuck.\n"
        "- Engineering owns recruiter.* logger namespace; on-call covers tick / daily-report job failures.",
    ),
    (
        "How do you gather, triage, and act on feedback and bugs? How are critical issues prioritized and communicated?",
        "- Triage daily report failures + planner FAILED campaigns weekly.\n"
        "- Critical issues (signups not attributing, sending SMS to opted-out contacts) treated as P0 with immediate kill-switch (per-tenant feature flag).\n"
        "- Internal channel for AI-quality issues (tone, hallucinations) — captured for prompt-evolution log.",
    ),
    (
        "What monitoring / logging is in place to spot operational / AI issues post-launch?",
        "- get_logger('recruiter.*') namespace for all events.\n"
        "- Existing token_usage table for LLM observability.\n"
        "- Admin notifications table available for surface-level alerts.\n"
        "- recruitment_reports table accumulates per-day narrative + payload for trend analysis.",
    ),
    (
        "How will you collect learnings, review performance, and update your system continuously post-launch?",
        "- recruitment_reports + recruitment_signups tables accumulate operational data.\n"
        "- After 30 days: calibrate overshoot_factor defaults from actual response rates by service.\n"
        "- Revisit experience-score weights if no_show rate stays high.\n"
        "- Quarterly review: prompt edits, scheduler-engine policy adjustments, new chat tools based on most-asked admin questions.",
    ),
]


def add_para(doc: Document, text: str) -> None:
    if text.startswith("- "):
        p = doc.add_paragraph(text[2:], style="List Bullet")
    else:
        p = doc.add_paragraph(text)
    for run in p.runs:
        run.font.size = Pt(11)


def main() -> None:
    out = Path(__file__).parent / "recruitment_agent_qa.docx"
    doc = Document()

    title = doc.add_heading(
        "Recruitment Agent – Project Q&A", level=0
    )
    sub = doc.add_paragraph(
        "AI-powered volunteer recruitment feature for the multi-tenant booking system."
    )
    for run in sub.runs:
        run.italic = True
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    for i, (q, a) in enumerate(QA, start=1):
        doc.add_heading(f"{i}. {q}", level=2)
        for block in a.split("\n\n"):
            for line in block.split("\n"):
                if line.strip():
                    add_para(doc, line)
            # blank paragraph between blocks for readability
            doc.add_paragraph("")

    doc.save(out)
    print(f"Wrote {out} ({len(QA)} Q&A entries)")


if __name__ == "__main__":
    main()
