"""Generate intent_architecture_brief.docx — executive briefing on the
hybrid intent-routing architecture for volunteer SMS.

Run: python docs/build_intent_architecture_brief_docx.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


# ── Content ─────────────────────────────────────────────────────────

TITLE = "Hybrid Intent Routing for Volunteer SMS"
SUBTITLE = (
    "Executive briefing — how our volunteer-message routing works, why we "
    "chose a layered approach, and how it compares to pure-rules and "
    "pure-AI alternatives."
)
VERSION_LINE = "Version 1.0 · June 2026"

EXECUTIVE_SUMMARY = (
    "Volunteers text our system thousands of times a day to check in, "
    "check out, and switch jobs mid-event. We chose a three-tier routing "
    "design that combines deterministic pattern matching, a fast lightweight "
    "AI classifier, and a full conversational AI as a fallback. This delivers "
    "the reliability of rules where it matters most, the flexibility of AI "
    "where the language gets creative, and total operating cost dominated by "
    "the cheapest tier — not the most expensive one."
)

DECISION_TLDR = (
    "We do NOT route every volunteer message through a large AI model. "
    "We do NOT rely on rigid keyword rules alone. Instead, the same message "
    "is filtered through three layers — each one only used when the previous "
    "one cannot give a confident answer. The end result: about 80–90% of "
    "messages are handled with zero AI cost in under 50 milliseconds, "
    "another 5–10% are caught by a low-cost classifier in ~300 ms, and the "
    "remaining tail goes to the full AI."
)

# Section: How a volunteer message flows
FLOW_INTRO = (
    "When a volunteer sends a text message, it enters our system and is "
    "routed through three tiers in sequence. The first tier that can "
    "confidently identify the volunteer's intent acts on it; the message "
    "never proceeds further."
)

TIER_TABLE_ROWS = [
    ["Tier", "What it is", "Speed", "Cost per message", "What it handles"],
    [
        "Tier 1 — Pattern Rules",
        "Predefined text patterns for canonical phrases",
        "~5 ms",
        "$0",
        "Standard phrases: HERE, DONE, switch to kitchen, etc.",
    ],
    [
        "Tier 2 — Light AI Classifier",
        "A small, fast AI model that only labels the intent (no conversation)",
        "~300 ms",
        "~$0.0001",
        "Variations: \"im finally here lol\", \"leaving now\", \"switching over to setup\"",
    ],
    [
        "Tier 3 — Full Conversational AI",
        "A large language model with full conversational tools",
        "~1–2 seconds",
        "~$0.005–0.015",
        "Open questions, multi-turn conversations, anything not a clear action",
    ],
]

# Section: The three architectural options considered
OPTIONS_INTRO = (
    "When designing this system, we considered three families of approaches. "
    "Each represents a different point on the same fundamental tradeoff: "
    "the more you delegate to AI, the more flexibility you get, but the more "
    "you spend, the slower it becomes, and the more probabilistic the behavior."
)

OPTION_A_TITLE = "Option A — Rules Only (no AI)"
OPTION_A_DESC = (
    "Every message is matched against a fixed library of text patterns. "
    "If a pattern matches, act. If nothing matches, send a generic \"I "
    "didn't understand\" reply. This is what early SMS-based check-in "
    "systems used in the 2010s."
)
OPTION_A_PROS = [
    "Zero AI cost per message — runs entirely on our own servers.",
    "Predictable and auditable — the system either matches or it doesn't.",
    "Instant response time, measured in single-digit milliseconds.",
    "Behavior is stable across software versions — no model drift.",
]
OPTION_A_CONS = [
    "Rigid: \"im finally here lol\" doesn't match \"HERE\" — the volunteer "
    "gets a confusing rejection.",
    "Engineering tax: every new phrasing the team discovers must be added "
    "by hand. Costly and never complete.",
    "Poor experience for free-text questions: \"what time do I arrive?\" "
    "gets a generic fallback even though we know the answer.",
    "Brittle to typos, abbreviations, voice-dictated mistakes, and emoji.",
]

OPTION_B_TITLE = "Option B — AI Only (every message goes through a large model)"
OPTION_B_DESC = (
    "Every inbound message — even a plain \"HERE\" from a volunteer at "
    "check-in — is sent to a large language model that decides what to do. "
    "This is what consumer assistants like ChatGPT do."
)
OPTION_B_PROS = [
    "Maximum flexibility — handles any phrasing the language allows.",
    "Single code path: no separate \"rules\" and \"AI\" logic to maintain.",
    "Conversational by default — can ask clarifying questions naturally.",
    "Picks up new behaviors as the underlying model improves.",
]
OPTION_B_CONS = [
    "Cost: every check-in, check-out, status ping, and STOP STATUS reply "
    "incurs full AI cost. For a 50-volunteer event with auto-pings, this "
    "is dollars per event, not cents. Multiplied by tens of events per "
    "tenant per month, it adds up materially.",
    "Latency: 1–2 seconds per message. When 30 volunteers arrive in a "
    "10-minute window, the cumulative wait time pushes some replies past "
    "the time the volunteer is already inside the building.",
    "Probabilistic behavior: a 99% reliable check-in still means roughly "
    "1 in 100 volunteers is misclassified. If the admin thinks a volunteer "
    "no-showed when they didn't, that's an operational failure that erodes "
    "trust.",
    "Hard to audit: \"why did the AI do that?\" doesn't have a deterministic "
    "answer, which makes compliance and post-incident review more difficult.",
    "Drift: when the AI vendor updates the underlying model, our system's "
    "behavior changes overnight without us touching the code.",
]

OPTION_C_TITLE = "Option C — Hybrid (chosen)"
OPTION_C_DESC = (
    "Three layers, each one acting as a safety net for the one above it. "
    "Pattern rules handle the canonical 80–90% of messages instantly and "
    "for free. A small, cheap AI model catches the long tail of natural "
    "phrasings. A full conversational AI handles everything else."
)
OPTION_C_PROS = [
    "Cost is dominated by the cheapest tier. Most check-ins, check-outs, "
    "and acknowledgements cost nothing.",
    "Reliability where it matters: \"HERE\" always means HERE. Critical "
    "operational moments — arrival and departure — are 100% deterministic.",
    "Flexibility where the language gets creative: the AI tier catches "
    "\"im on my way actually\", \"leaving in 5\", or \"switching gears to "
    "setup\".",
    "Conversational fallback for open-ended questions: free-text questions "
    "(\"where do I park?\") still get a smart answer.",
    "Predictable cost ceiling: even if we doubled volunteer volume, the AI "
    "cost only grows with the long-tail messages, not the total.",
    "Each tier is independently auditable: pattern matches are logged with "
    "the matching rule, classifier decisions are logged with their "
    "confidence score, full-AI conversations are logged with their tool "
    "calls.",
]
OPTION_C_CONS = [
    "More moving parts to maintain — three layers instead of one.",
    "Requires careful prompt and threshold tuning to make sure the AI "
    "classifier defers gracefully when uncertain.",
    "A volunteer who phrases something unusually may experience slightly "
    "longer reply latency (~300 ms instead of ~5 ms) when Tier 2 fires.",
    "Engineering effort up front to build the tier-2 classifier and "
    "thresholds — roughly two days for our team to wire it in.",
]

# Comparison table
COMPARISON_ROWS = [
    ["Dimension", "Rules Only", "AI Only", "Hybrid (chosen)"],
    ["Typical latency", "~5 ms", "~1–2 sec", "~5 ms (T1) / ~300 ms (T2) / ~1–2 sec (T3)"],
    ["AI cost / message", "$0", "$0.005–0.015", "$0 for most; ~$0.0001 average"],
    ["Reliability on canonical phrases", "Perfect", "~99%", "Perfect (T1 handles them)"],
    ["Flexibility on novel phrasings", "None", "High", "High via T2 fallback"],
    ["Auditability", "Excellent", "Limited", "Excellent per-tier"],
    ["Engineering investment", "Low up front, high ongoing", "Low all around", "Medium up front, low ongoing"],
    ["Stable across model upgrades", "Yes", "No (drifts)", "Tier 1 stable; T2/T3 inherit any drift"],
    ["Handles open questions", "No", "Yes", "Yes via T3"],
    ["Operating cost scales with…", "Engineering hours", "Message volume", "Long-tail message volume"],
]

# Section: Production behavior
BEHAVIOR_INTRO = (
    "Below are the kinds of messages each tier handles in practice. The "
    "exact split varies by tenant, but the cost and latency profile of the "
    "system is set by Tier 1's coverage of the canonical 80–90%."
)

BEHAVIOR_ROWS = [
    ["Message from volunteer", "Tier that handles it", "Cost", "Outcome"],
    ["HERE", "Tier 1 (rules)", "$0", "Instant check-in"],
    ["DONE", "Tier 1 (rules)", "$0", "Instant check-out"],
    ["switch to kitchen", "Tier 1 (rules)", "$0", "Service-change request created"],
    ["im finally here lol", "Tier 2 (classifier)", "~$0.0001", "Check-in"],
    ["leaving now", "Tier 2 (classifier)", "~$0.0001", "Check-out"],
    ["moving over to setup actually", "Tier 2 (classifier)", "~$0.0001", "Service-change request"],
    ["what time is the gala?", "Tier 3 (full AI)", "~$0.01", "Answered from event data"],
    ["where do I park?", "Tier 3 (full AI)", "~$0.01", "Answered from event location"],
    ["might leave in a bit", "Tier 3 (full AI)", "~$0.01", "Tentative — AI asks for confirmation"],
]

# Section: Business implications
IMPLICATIONS_PARAS = [
    (
        "Cost predictability",
        "Operating cost grows with the number of messages that require AI "
        "interpretation, not with total message volume. This decouples our "
        "AI spend from raw growth — if a tenant doubles their volunteer "
        "base, the bulk of those additional check-ins still cost nothing.",
    ),
    (
        "Reliability of mission-critical moments",
        "Volunteer check-in and check-out are the operational moments where "
        "errors are most visible (a volunteer marked as no-show who actually "
        "showed). By keeping these on the deterministic tier, we make these "
        "moments perfectly reliable. The AI handles the parts of the "
        "conversation where being wrong is recoverable.",
    ),
    (
        "Margin protection at scale",
        "If we had committed to an AI-only architecture, our gross margin "
        "on each tenant would be tied to inbound message volume — and the "
        "more successful a tenant became, the worse our margins. The "
        "hybrid design pins our AI cost near zero for the dominant use "
        "case and lets us hold pricing flat as tenants scale.",
    ),
    (
        "Resilience to AI vendor changes",
        "When our AI vendor updates their underlying model, our most "
        "common operations (check-in, check-out, mid-event switches, "
        "auto-pings, recognition awards) are unaffected — they run on "
        "deterministic code. The AI tiers can be re-tested, re-tuned, "
        "or temporarily disabled without disrupting day-to-day operations.",
    ),
    (
        "Faster product iteration",
        "Adding a new operational behavior (e.g., \"volunteer texts BUSY "
        "to defer a check-in window\") takes hours, not weeks. We add the "
        "deterministic handler and an entry in the classifier prompt; the "
        "system picks up both canonical and creative phrasings on the "
        "next deploy.",
    ),
]

# Section: When this decision might change
REVISIT_INTRO = (
    "The hybrid choice is the right answer for the system we operate today. "
    "Three plausible futures would change the calculus:"
)
REVISIT_BULLETS = [
    "Per-message AI cost drops by 100×. If model prices fall to the point "
    "where running every message through the full AI costs less than $0.0001, "
    "Tier 1 and Tier 2 become engineering overhead rather than cost savings. "
    "We would simplify to AI-only.",
    "Model reliability on canonical commands reaches deterministic levels. "
    "If a future model can be guaranteed to interpret \"HERE\" correctly "
    "every single time across millions of messages, the case for the rule "
    "tier weakens. (Today this isn't a guarantee any model vendor offers.)",
    "Volunteer language complexity outgrows the classifier tier. If we "
    "expand into languages, regions, or domains where the long-tail "
    "phrasings are 50%+ of messages instead of 5–10%, Tier 2 starts "
    "carrying most of the load and the case for a simpler two-tier "
    "stack (no Tier 1) gets stronger.",
]

CLOSING_NOTE = (
    "In short: we built a system where the cheapest, fastest, most reliable "
    "tier handles the largest share of traffic, and AI is reserved for the "
    "moments where it adds real value. This is the right architecture for "
    "SMS-based volunteer operations today, and the costs and tradeoffs "
    "remain visible enough that we can revisit the choice if the underlying "
    "economics shift."
)


# ── Word document construction ─────────────────────────────────────

def _set_cell_shading(cell, color_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def _set_run_color(run, rgb: RGBColor) -> None:
    run.font.color.rgb = rgb


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
        _set_run_color(run, RGBColor(0x55, 0x55, 0x55))


def _add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        for run in p.runs:
            run.font.size = Pt(11)


def _add_table(
    doc: Document,
    rows: list[list[str]],
    *,
    header_shade: str = "E8EEF7",
    first_col_emphasis: bool = False,
) -> None:
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    for r_idx, row in enumerate(rows):
        for c_idx in range(ncols):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = ""
            text = row[c_idx] if c_idx < len(row) else ""
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(10)
            if r_idx == 0:
                run.bold = True
                _set_cell_shading(cell, header_shade)
            elif first_col_emphasis and c_idx == 0:
                run.bold = True
    doc.add_paragraph("")


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


def build(out_path: Path) -> None:
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    # Title block
    _add_heading(doc, TITLE, level=0)
    _add_paragraph(doc, SUBTITLE, italic=True)
    _add_paragraph(doc, VERSION_LINE, italic=True)
    _add_horizontal_rule(doc)

    # Executive Summary
    _add_heading(doc, "Executive Summary", level=1)
    _add_paragraph(doc, EXECUTIVE_SUMMARY)

    _add_heading(doc, "The Decision in One Paragraph", level=1)
    _add_paragraph(doc, DECISION_TLDR)
    _add_horizontal_rule(doc)

    # How the routing works
    _add_heading(doc, "How a Volunteer Message Flows", level=1)
    _add_paragraph(doc, FLOW_INTRO)
    _add_table(doc, TIER_TABLE_ROWS, first_col_emphasis=True)

    _add_horizontal_rule(doc)

    # The three options
    _add_heading(doc, "The Three Architectural Options We Considered", level=1)
    _add_paragraph(doc, OPTIONS_INTRO)

    for title, desc, pros, cons in (
        (OPTION_A_TITLE, OPTION_A_DESC, OPTION_A_PROS, OPTION_A_CONS),
        (OPTION_B_TITLE, OPTION_B_DESC, OPTION_B_PROS, OPTION_B_CONS),
        (OPTION_C_TITLE, OPTION_C_DESC, OPTION_C_PROS, OPTION_C_CONS),
    ):
        _add_heading(doc, title, level=2)
        _add_paragraph(doc, desc)

        _add_paragraph(doc, "Strengths:")
        _add_bullets(doc, pros)

        _add_paragraph(doc, "Limitations:")
        _add_bullets(doc, cons)

    _add_horizontal_rule(doc)

    # Side-by-side comparison
    _add_heading(doc, "Side-by-Side Comparison", level=1)
    _add_paragraph(
        doc,
        "Each dimension below compares the three approaches across the "
        "criteria executives most often ask about: cost, latency, "
        "reliability, and operational risk.",
    )
    _add_table(doc, COMPARISON_ROWS, first_col_emphasis=True)

    _add_horizontal_rule(doc)

    # Production behavior
    _add_heading(doc, "What This Looks Like in Practice", level=1)
    _add_paragraph(doc, BEHAVIOR_INTRO)
    _add_table(doc, BEHAVIOR_ROWS, first_col_emphasis=True)

    _add_horizontal_rule(doc)

    # Business implications
    _add_heading(doc, "Why This Matters for the Business", level=1)
    for heading, body in IMPLICATIONS_PARAS:
        _add_heading(doc, heading, level=2)
        _add_paragraph(doc, body)

    _add_horizontal_rule(doc)

    # When to revisit
    _add_heading(doc, "When This Decision Should Be Revisited", level=1)
    _add_paragraph(doc, REVISIT_INTRO)
    _add_bullets(doc, REVISIT_BULLETS)

    _add_horizontal_rule(doc)

    # Closing
    _add_heading(doc, "Bottom Line", level=1)
    _add_paragraph(doc, CLOSING_NOTE)

    doc.save(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    here = Path(__file__).parent
    build(here / "intent_architecture_brief.docx")


if __name__ == "__main__":
    main()
