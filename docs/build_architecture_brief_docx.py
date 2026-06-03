"""Generate architecture_brief.docx — executive architecture brief
covering the whole application.

Run: python docs/build_architecture_brief_docx.py

Inputs: docs/architecture_diagram.png (build with build_architecture_diagram.py)
Output: docs/architecture_brief.docx
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


# ── Content ─────────────────────────────────────────────────────────

TITLE = "Volunteer Engagement Platform — Architecture Overview"
SUBTITLE = (
    "Executive briefing — what the system is, how it is structured, the "
    "architectural patterns it implements, and the choices we want "
    "leadership to understand."
)
VERSION_LINE = "Version 1.0 · June 2026"

EXECUTIVE_SUMMARY = (
    "We operate a multi-tenant SaaS platform that automates volunteer "
    "operations for nonprofits, faith communities, and event organizers. "
    "The product is SMS-first: volunteers interact entirely by text "
    "message, and admins use a web panel plus an SMS command channel. "
    "AI is woven throughout — but used selectively, behind a layered "
    "system that prioritizes reliability and cost control over showy "
    "AI everywhere. The architecture is designed around three guiding "
    "principles: every tenant's data is strictly isolated; the "
    "cheapest, fastest, most reliable path handles the dominant case; "
    "and every decision the system makes is auditable after the fact."
)

# ── System overview ──
WHAT_THE_SYSTEM_IS = (
    "The platform handles the full operational lifecycle of a volunteer "
    "event: scheduling, recruiting volunteers via targeted SMS waves, "
    "booking them into specific service slots, sending reminders, "
    "processing day-of check-in and check-out (also by SMS), handling "
    "mid-event role changes, capturing post-event quality reviews, and "
    "awarding milestones, badges, and other recognition. A separate "
    "donations track is in development. The same backend serves an "
    "admin web panel, a Twilio SMS endpoint for inbound volunteer "
    "messages, and a scheduler that runs background jobs."
)

# ── Diagram caption ──
DIAGRAM_CAPTION = (
    "Figure 1. System architecture across five horizontal layers: "
    "external channels at the top, application core, the agent layer, "
    "the hybrid intent stack, and data + external integrations at the "
    "bottom. Solid arrows show primary request flow; dashed arrows show "
    "background work and cross-cutting writes."
)

# ── Architectural patterns ──
PATTERNS_INTRO = (
    "The architecture implements ten patterns we want leadership to "
    "understand at a conceptual level. Each section explains what the "
    "pattern is, why it was chosen, and what the business benefit is."
)

PATTERNS = [
    {
        "name": "1. Multi-Tenant Row-Level Isolation",
        "what": (
            "Every record in our database — contacts, bookings, "
            "conversations, settings, AI prompts, credentials — is tagged "
            "with the tenant it belongs to. Every database query the "
            "application makes automatically scopes by that tenant. There "
            "is no shared data across tenants except platform-level "
            "infrastructure."
        ),
        "why": (
            "We chose row-level isolation over per-tenant databases or "
            "per-tenant servers because it gives us the strongest tenant "
            "boundary at the lowest operating cost. We can onboard a new "
            "tenant in minutes instead of hours, deploy schema changes once "
            "instead of per-tenant, and keep our cloud bill flat as the "
            "tenant count grows. The trade-off — that we depend on "
            "application-level scoping — is mitigated by making tenant "
            "scoping part of every shared base query, so no developer can "
            "accidentally write a tenant-leaking query."
        ),
        "benefit": (
            "Faster onboarding, lower marginal cost per tenant, simpler "
            "operations. Each tenant carries its own Twilio number, "
            "Anthropic key, Google Calendar credentials, and SMS prompts — "
            "stored on its tenant row — so credential changes do not "
            "require redeploys."
        ),
    },
    {
        "name": "2. Path-A Agent Architecture",
        "what": (
            "The AI-driven parts of the system are organized into four "
            "specialized 'agents': an Orchestrator that decides which "
            "agent should handle a message, an Engagement Agent that "
            "owns the live event lifecycle, a Recruiter + Scheduler "
            "Agent that fills events, and a Marketing Agent (in design) "
            "that runs donation campaigns. Each agent follows the same "
            "internal shape — planner, executor, reporter, intents — "
            "so the code is uniform across agents."
        ),
        "why": (
            "Without this structure, AI features tend to sprawl into a "
            "single overgrown handler that is hard to test, debug, or "
            "modify safely. The agent shape forces a separation between "
            "deciding what to do, doing it, and explaining what was "
            "done. This makes it possible to swap one agent's "
            "implementation without touching the others, and gives us a "
            "clean seam where new agents can be added later."
        ),
        "benefit": (
            "Faster feature delivery, lower regression risk, easier "
            "onboarding for new engineers. The agent boundary is also a "
            "natural place to attribute cost and observability — we can "
            "see at a glance which agent is consuming AI budget."
        ),
    },
    {
        "name": "3. Hybrid Intent Stack (regex → small AI → full AI)",
        "what": (
            "Every inbound volunteer or admin message passes through up "
            "to three tiers: deterministic pattern rules, a fast lightweight "
            "AI classifier, and a full conversational AI as a fallback. "
            "Each tier hands off to the next only when it cannot answer "
            "confidently."
        ),
        "why": (
            "We weighed pure-rules (too rigid, breaks on phrasing "
            "variations) and pure-AI (too expensive and too slow at "
            "scale, and probabilistic on mission-critical actions). The "
            "tiered design gives us the cost and reliability profile of "
            "rules for the dominant 80–90% of messages while still "
            "handling the long tail gracefully. See the companion "
            "document 'Hybrid Intent Routing for Volunteer SMS' for the "
            "full comparison."
        ),
        "benefit": (
            "AI cost is dominated by the cheapest tier. Check-in and "
            "check-out — the mission-critical operational moments — are "
            "100% deterministic. Long-tail phrasings still work. Gross "
            "margin is decoupled from message volume."
        ),
    },
    {
        "name": "4. Webhook Buffer (return-fast, process-later)",
        "what": (
            "When a volunteer's SMS arrives at our Twilio webhook, we "
            "acknowledge it within ~30 milliseconds and process the "
            "message in the background. The volunteer's reply is sent "
            "separately, after processing completes."
        ),
        "why": (
            "Twilio enforces strict response timeouts on its webhooks. "
            "If our application stalls — say, the AI vendor is "
            "temporarily slow — we still owe Twilio a fast response, or "
            "the message gets retried, duplicated, or lost. Returning "
            "immediately and processing in the background isolates "
            "carrier reliability from application reliability."
        ),
        "benefit": (
            "We can take seconds to process a message without ever "
            "missing a webhook. Carrier-side retries do not turn into "
            "duplicate check-ins. The system stays responsive under "
            "load."
        ),
    },
    {
        "name": "5. Graceful Degradation of External Dependencies",
        "what": (
            "Every external service we depend on — Twilio, Anthropic, "
            "Google Calendar, Resend, Supabase Auth — is wrapped in a "
            "soft-fail pattern. If the service is slow or down, the "
            "application falls back to a safe default rather than "
            "blocking or erroring."
        ),
        "why": (
            "External services have their own outages, rate limits, and "
            "latency spikes. If a single external dependency could "
            "block our entire platform, our uptime ceiling would be the "
            "product of all of them — which is much lower than any "
            "individual vendor's SLA. Soft-failing means a temporary "
            "vendor issue degrades a feature, not the whole product."
        ),
        "benefit": (
            "Higher effective uptime than any single vendor offers. "
            "Cost predictability — a vendor outage does not snowball "
            "into emergency engineering work."
        ),
    },
    {
        "name": "6. Optimistic Concurrency Control",
        "what": (
            "Records that can be modified by both volunteers and admins "
            "simultaneously — pending service-change approvals, "
            "bookings, conversation state — carry a version number. "
            "Updates check that the version still matches; if a "
            "different writer got there first, the operation fails "
            "cleanly with a 'please retry' signal."
        ),
        "why": (
            "On a busy event, an admin might be approving a service "
            "change at the same moment the volunteer is texting a new "
            "request. Locking the record would queue admin actions "
            "behind volunteer SMS, which is the wrong priority order. "
            "Optimistic concurrency lets both operations proceed in "
            "parallel and only intervenes when there is a real "
            "collision."
        ),
        "benefit": (
            "No lock contention on hot rows during peak event traffic. "
            "Admins see clean retry prompts on the rare collision, "
            "rather than mysterious stalls."
        ),
    },
    {
        "name": "7. Graph-Shaped Audit Trail",
        "what": (
            "Every routing decision the system makes — which agent "
            "handled a message, which tier of the intent stack fired, "
            "which AI tool was invoked, how much each operation cost — "
            "is recorded in a structured audit log. The log captures "
            "the relationships between events (this turn fired these "
            "tools, which produced this reply), not just a flat list."
        ),
        "why": (
            "An AI-assisted system that cannot explain its own behavior "
            "is a compliance and support liability. We made the deliberate "
            "choice to capture the structured chain of decisions as a "
            "graph so that the answer to 'why did the system send this "
            "reply?' is always available — for compliance, customer "
            "support, and product iteration."
        ),
        "benefit": (
            "Fast incident triage. Compliance-friendly audit posture. "
            "Direct visibility into where AI cost is being spent."
        ),
    },
    {
        "name": "8. Domain-Driven Folder Structure",
        "what": (
            "Both the backend and frontend are organized into feature "
            "folders that mirror business domains: bookings, "
            "recruitment, conversations, recognition, observability, "
            "and so on. Each domain owns its own data access, business "
            "logic, and UI components."
        ),
        "why": (
            "When code is organized by technical layer (controllers, "
            "services, models), changes to a single feature touch every "
            "layer and the diff is hard to review. Organizing by domain "
            "keeps related code together, so a feature change is a "
            "self-contained, reviewable unit."
        ),
        "benefit": (
            "Faster feature delivery, smaller pull requests, lower "
            "review overhead. New engineers can ship to a single domain "
            "before needing to understand the whole system."
        ),
    },
    {
        "name": "9. Per-Tenant Configuration Surface",
        "what": (
            "Tenant-specific behavior — SMS prompts, feature flags, "
            "external credentials, AI model preferences, recognition "
            "definitions, opt-in messaging — lives in a key-value "
            "configuration table scoped to the tenant. Admins can edit "
            "this from the web panel; changes apply on the next message."
        ),
        "why": (
            "Tenants serve different communities and have different "
            "voices. Hard-coding behavior would force us to fork the "
            "codebase per tenant or ship surveys of 'preferences' in "
            "code. The configuration table lets a tenant customize "
            "voice, messaging, and operational rules without engineering "
            "involvement."
        ),
        "benefit": (
            "Tenants self-serve their own customization. Engineering "
            "stays focused on platform work rather than per-tenant "
            "tweaks. Compliance with each tenant's brand and tone."
        ),
    },
    {
        "name": "10. Two-Sided LLM Personas",
        "what": (
            "When the AI does need to converse, it does so with one of "
            "two personas: a customer-facing persona for volunteers and "
            "an admin-facing persona for staff. Each has its own system "
            "prompt, its own set of tools, and its own context blocks. "
            "Volunteers never see admin tools; admins never see customer "
            "tools."
        ),
        "why": (
            "A single shared persona forces every tool call to defend "
            "against the wrong audience using it — a customer "
            "accidentally invoking an admin operation, or vice versa. "
            "Splitting the persona at the entry point pushes that "
            "concern into the routing layer where it belongs, instead "
            "of into every individual tool."
        ),
        "benefit": (
            "Smaller attack surface. Clearer tool semantics. Each "
            "persona can be tuned independently for its audience without "
            "regression risk on the other."
        ),
    },
]

# ── Cross-cutting design choices ──
HIGHLIGHTS_INTRO = (
    "Beyond the named patterns, there are five design choices we want "
    "leadership to be able to defend in conversations with prospects, "
    "investors, and auditors."
)

HIGHLIGHTS = [
    (
        "Cost-tiered AI",
        "AI cost grows with message complexity, not with message volume. "
        "Our dominant operations — check-in, check-out, status pings, "
        "reminders — are deterministic and cost nothing per message. "
        "This is the difference between a tenant doubling their "
        "volunteer base and our cost staying flat, versus our cost "
        "doubling with them.",
    ),
    (
        "Mission-critical reliability",
        "The operational moments where errors are most visible — a "
        "volunteer marked as no-show who actually arrived — are handled "
        "by deterministic code, not probabilistic AI. We accept slightly "
        "less flexibility in those moments in exchange for perfect "
        "reliability.",
    ),
    (
        "Vendor diversification by design",
        "We depend on Twilio (SMS), Anthropic (AI), Supabase "
        "(PostgreSQL + Auth), Google (Calendar), and Resend (Email). "
        "Each integration is wrapped so that a vendor outage degrades "
        "one capability rather than breaking the platform. Replacing "
        "any vendor is a contained engineering project, not a rewrite.",
    ),
    (
        "Auditable by default",
        "Every routing decision, every AI invocation, every state "
        "change is recorded in a structured log. We can answer 'what "
        "did the system do and why?' for any message after the fact. "
        "This matters for compliance, customer support, and incident "
        "review.",
    ),
    (
        "Single-product, multi-tenant",
        "We chose row-level multi-tenancy from the beginning rather "
        "than starting single-tenant and retrofitting later. Onboarding "
        "a new tenant takes minutes. Schema migrations apply once. Our "
        "marginal cost per tenant is dominated by usage, not "
        "infrastructure overhead.",
    ),
]

# ── Why these choices — strategic framing ──
STRATEGIC_INTRO = (
    "Three strategic concerns shaped the architecture as a whole, and "
    "are worth making explicit:"
)

STRATEGIC_BULLETS = [
    (
        "Margin protection at scale. Every architectural choice that "
        "moves work onto deterministic, in-process code instead of "
        "external AI calls protects our gross margin as tenants grow. "
        "This is the difference between a profitable scale story and "
        "an AI-cost-eats-revenue story."
    ),
    (
        "Operational trust. Volunteer operations is a domain where "
        "missed check-ins, lost confirmations, and silent failures "
        "directly damage customer relationships. The architecture is "
        "tilted toward reliability — soft-failing dependencies, "
        "audit logs, deterministic routing — because the reputational "
        "cost of a quiet bug is higher than the engineering cost of "
        "preventing it."
    ),
    (
        "Optionality. The agent layer, the per-tenant configuration "
        "surface, and the soft-failing external-dependency pattern "
        "together mean that future changes — adding a new agent, "
        "swapping an AI vendor, supporting a new SMS provider — are "
        "contained refactors, not platform rewrites. This is what makes "
        "future product bets cheap."
    ),
]

# ── Where we are headed ──
ROADMAP_INTRO = (
    "Several enhancements are in flight or designed but not yet built. "
    "Each is a deliberate extension of the architecture rather than a "
    "redesign:"
)

ROADMAP_BULLETS = [
    "Donation campaigns and a Marketing Agent with a public donation "
    "page and pluggable payment processors.",
    "Semantic search powered by pgvector + Voyage AI embeddings, for "
    "conversation recall and similar-past-event suggestions.",
    "Pluggable external contact data sources so a tenant's CRM, "
    "HRIS, or identity provider can be the source of truth for "
    "volunteer profiles.",
    "An MCP server surface so external AI agents (Claude Desktop, "
    "Cursor, tenant-built tools) can integrate with our platform.",
    "Twilio sub-account provisioning for per-tenant SMS isolation, "
    "billing attribution, and 10DLC registration.",
    "Issue-reporting pipeline (hallucinations, system errors, customer "
    "feedback) with LLM classification routing to the right inbox.",
]

CLOSING_NOTE = (
    "The headline is that we have built — and continue to build — a "
    "platform that uses AI as a tool, not as a magic wand. The "
    "architecture is opinionated about where AI adds value, where it "
    "doesn't, and how to make sure the cost and reliability tradeoffs "
    "are visible and reversible. This is the foundation that lets us "
    "scale tenants without scaling cost, defend our gross margin in an "
    "AI-priced market, and ship new product surfaces without rewriting "
    "what already works."
)


# ── Word document construction ─────────────────────────────────────

def _set_cell_shading(cell, color_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def _add_heading(doc: Document, text: str, level: int) -> None:
    h = doc.add_heading(level=level)
    run = h.add_run(text)
    if level == 0:
        run.font.size = Pt(22)
    elif level == 1:
        run.font.size = Pt(15)
    elif level == 2:
        run.font.size = Pt(13)


def _add_paragraph(doc: Document, text: str, *, italic: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(11)
    if italic:
        run.italic = True
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def _add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        for run in p.runs:
            run.font.size = Pt(11)


def _add_horizontal_rule(doc: Document) -> None:
    p = doc.add_paragraph()
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "AAAAAA")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _add_pattern_block(doc: Document, pattern: dict) -> None:
    _add_heading(doc, pattern["name"], level=2)

    p = doc.add_paragraph()
    r = p.add_run("What it is. ")
    r.bold = True
    r.font.size = Pt(11)
    p.add_run(pattern["what"]).font.size = Pt(11)

    p = doc.add_paragraph()
    r = p.add_run("Why we chose it. ")
    r.bold = True
    r.font.size = Pt(11)
    p.add_run(pattern["why"]).font.size = Pt(11)

    p = doc.add_paragraph()
    r = p.add_run("Business benefit. ")
    r.bold = True
    r.font.size = Pt(11)
    p.add_run(pattern["benefit"]).font.size = Pt(11)


def _add_highlight_block(doc: Document, title: str, body: str) -> None:
    p = doc.add_paragraph()
    r = p.add_run(f"{title}. ")
    r.bold = True
    r.font.size = Pt(11)
    p.add_run(body).font.size = Pt(11)


def build(out_path: Path, diagram_path: Path) -> None:
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    # ── Title ──
    _add_heading(doc, TITLE, level=0)
    _add_paragraph(doc, SUBTITLE, italic=True)
    _add_paragraph(doc, VERSION_LINE, italic=True)
    _add_horizontal_rule(doc)

    # ── Executive summary ──
    _add_heading(doc, "Executive Summary", level=1)
    _add_paragraph(doc, EXECUTIVE_SUMMARY)

    # ── What the system is ──
    _add_heading(doc, "What the System Does", level=1)
    _add_paragraph(doc, WHAT_THE_SYSTEM_IS)

    _add_horizontal_rule(doc)

    # ── Diagram ──
    _add_heading(doc, "Architecture Diagram", level=1)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if diagram_path.exists():
        p.add_run().add_picture(str(diagram_path), width=Inches(6.5))
    else:
        p.add_run(
            f"[Diagram missing — run build_architecture_diagram.py first. "
            f"Expected at {diagram_path}]"
        )

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run(DIAGRAM_CAPTION)
    cr.italic = True
    cr.font.size = Pt(9.5)
    cr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    _add_horizontal_rule(doc)

    # ── Architectural patterns ──
    _add_heading(doc, "Key Architectural Patterns We Implemented", level=1)
    _add_paragraph(doc, PATTERNS_INTRO)

    for pattern in PATTERNS:
        _add_pattern_block(doc, pattern)

    _add_horizontal_rule(doc)

    # ── Cross-cutting highlights ──
    _add_heading(doc, "Key Points to Highlight", level=1)
    _add_paragraph(doc, HIGHLIGHTS_INTRO)
    for title, body in HIGHLIGHTS:
        _add_highlight_block(doc, title, body)

    _add_horizontal_rule(doc)

    # ── Strategic framing ──
    _add_heading(doc, "Strategic Concerns That Shaped the Architecture", level=1)
    _add_paragraph(doc, STRATEGIC_INTRO)
    _add_bullets(doc, STRATEGIC_BULLETS)

    _add_horizontal_rule(doc)

    # ── Roadmap / extensibility ──
    _add_heading(doc, "What This Architecture Sets Us Up to Do Next", level=1)
    _add_paragraph(doc, ROADMAP_INTRO)
    _add_bullets(doc, ROADMAP_BULLETS)

    _add_horizontal_rule(doc)

    # ── Closing ──
    _add_heading(doc, "Bottom Line", level=1)
    _add_paragraph(doc, CLOSING_NOTE)

    doc.save(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    here = Path(__file__).parent
    build(
        out_path=here / "architecture_brief.docx",
        diagram_path=here / "architecture_diagram.png",
    )


if __name__ == "__main__":
    main()
