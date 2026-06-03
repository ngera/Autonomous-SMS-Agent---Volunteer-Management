"""Generate architecture_brief.pptx — executive slide deck.

Run: python docs/build_architecture_brief_pptx.py
Inputs: docs/architecture_diagram.png
Output: docs/architecture_brief.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu


# ── Palette ────────────────────────────────────────────────────────
BG_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TXT_DARK = RGBColor(0x1A, 0x1A, 0x1A)
TXT_BODY = RGBColor(0x2C, 0x2C, 0x2C)
TXT_MUTE = RGBColor(0x55, 0x55, 0x55)
TXT_LIGHT = RGBColor(0x88, 0x88, 0x88)
DIVIDER = RGBColor(0xDD, 0xDD, 0xDD)

# Accent colors — keyed to the diagram so visuals feel consistent
ACCENT_BLUE = RGBColor(0x5B, 0x7A, 0xB8)
ACCENT_SAGE = RGBColor(0x7B, 0xA0, 0x70)
ACCENT_PEACH = RGBColor(0xC5, 0x8A, 0x6B)
ACCENT_LAVENDER = RGBColor(0x94, 0x74, 0xA6)
ACCENT_WARM = RGBColor(0x9C, 0x8F, 0x76)

CALLOUT_BLUE = RGBColor(0xE8, 0xEE, 0xF7)
CALLOUT_SAGE = RGBColor(0xE4, 0xED, 0xE3)
CALLOUT_PEACH = RGBColor(0xF5, 0xE6, 0xE0)
CALLOUT_LAVENDER = RGBColor(0xED, 0xE3, 0xF2)
CALLOUT_WARM = RGBColor(0xF1, 0xEC, 0xE4)


# ── Geometry (16:9 widescreen at 13.333 x 7.5 inches) ──
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# Vertical rhythm
TITLE_TOP = Inches(0.45)
TITLE_HEIGHT = Inches(0.85)
SUBTITLE_TOP = Inches(1.25)
CONTENT_TOP = Inches(1.95)
FOOTER_TOP = Inches(7.05)

# Horizontal rhythm
LEFT_MARGIN = Inches(0.7)
RIGHT_MARGIN = Inches(0.7)
CONTENT_WIDTH = SLIDE_W - LEFT_MARGIN - RIGHT_MARGIN


# ── Helpers ────────────────────────────────────────────────────────

def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    *,
    font_size: int = 14,
    color: RGBColor = TXT_BODY,
    bold: bool = False,
    italic: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = "Calibri"
    run.font.size = Pt(font_size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    return box


def add_bullet_list(
    slide,
    left,
    top,
    width,
    height,
    items: list[str],
    *,
    font_size: int = 16,
    color: RGBColor = TXT_BODY,
    line_spacing: float = 1.25,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_spacing
        run = p.add_run()
        run.text = f"•   {item}"
        run.font.name = "Calibri"
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        if i > 0:
            p.space_before = Pt(8)
    return box


def add_rect(
    slide,
    left,
    top,
    width,
    height,
    *,
    fill: RGBColor,
    line: RGBColor | None = None,
    rounded: bool = True,
):
    shape_type = (
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    )
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    return shape


def add_divider(slide, top: float):
    line = slide.shapes.add_connector(
        1,
        LEFT_MARGIN,
        Inches(top),
        SLIDE_W - RIGHT_MARGIN,
        Inches(top),
    )
    line.line.color.rgb = DIVIDER
    line.line.width = Pt(0.75)


def add_title(slide, title: str, eyebrow: str | None = None):
    if eyebrow:
        add_textbox(
            slide,
            LEFT_MARGIN, TITLE_TOP - Inches(0.05),
            CONTENT_WIDTH, Inches(0.3),
            eyebrow.upper(),
            font_size=10, color=ACCENT_BLUE, bold=True,
        )
        add_textbox(
            slide,
            LEFT_MARGIN, TITLE_TOP + Inches(0.25),
            CONTENT_WIDTH, TITLE_HEIGHT,
            title,
            font_size=28, color=TXT_DARK, bold=True,
        )
    else:
        add_textbox(
            slide,
            LEFT_MARGIN, TITLE_TOP,
            CONTENT_WIDTH, TITLE_HEIGHT,
            title,
            font_size=28, color=TXT_DARK, bold=True,
        )
    add_divider(slide, 1.45 if not eyebrow else 1.65)


def add_footer(slide, page_num: int, total: int):
    add_textbox(
        slide,
        LEFT_MARGIN, FOOTER_TOP,
        CONTENT_WIDTH, Inches(0.3),
        "Architecture Brief · Volunteer Engagement Platform",
        font_size=9, color=TXT_LIGHT, align=PP_ALIGN.LEFT,
    )
    add_textbox(
        slide,
        LEFT_MARGIN, FOOTER_TOP,
        CONTENT_WIDTH, Inches(0.3),
        f"{page_num} / {total}",
        font_size=9, color=TXT_LIGHT, align=PP_ALIGN.RIGHT,
    )


# ── Slide builders ─────────────────────────────────────────────────

def slide_title(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # Soft accent strip on the left
    add_rect(slide, Inches(0), Inches(0), Inches(0.35), SLIDE_H,
             fill=ACCENT_BLUE, rounded=False)

    add_textbox(
        slide, Inches(1.0), Inches(2.4),
        Inches(11.3), Inches(0.4),
        "ARCHITECTURE OVERVIEW", font_size=12,
        color=ACCENT_BLUE, bold=True,
    )
    add_textbox(
        slide, Inches(1.0), Inches(2.9),
        Inches(11.3), Inches(1.5),
        "Volunteer Engagement Platform",
        font_size=44, color=TXT_DARK, bold=True,
    )
    add_textbox(
        slide, Inches(1.0), Inches(4.2),
        Inches(11.3), Inches(1.0),
        "Multi-tenant SaaS  ·  SMS-first volunteer operations  ·  AI-assisted",
        font_size=18, color=TXT_MUTE, italic=True,
    )
    add_textbox(
        slide, Inches(1.0), Inches(6.7),
        Inches(11.3), Inches(0.4),
        "Executive briefing  ·  June 2026",
        font_size=12, color=TXT_LIGHT,
    )
    return slide


def slide_what_we_built(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "What we built", eyebrow="The platform")

    add_textbox(
        slide, LEFT_MARGIN, Inches(2.0),
        CONTENT_WIDTH, Inches(0.8),
        "A multi-tenant SaaS that automates the full operational lifecycle of "
        "volunteer events — from recruiting and booking, through day-of "
        "check-in and check-out, to post-event review and recognition.",
        font_size=18, color=TXT_BODY,
    )

    # Three pillar boxes
    pillars = [
        ("Multi-tenant",
         "Each tenant has its own data, credentials, prompts, and brand voice. "
         "Row-level isolation across every table.",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("SMS-first",
         "Volunteers interact entirely by text. Admins use a web panel plus an "
         "SMS command channel for day-of operations.",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("AI as a tool",
         "AI is used where it adds value. The dominant operations run on "
         "deterministic code that costs nothing per message.",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
    ]
    box_w = Inches(3.85)
    gap = Inches(0.25)
    start_left = LEFT_MARGIN + Inches(0.05)
    for i, (title, body, fill, edge) in enumerate(pillars):
        left = start_left + (box_w + gap) * i
        add_rect(slide, left, Inches(4.0), box_w, Inches(2.5),
                 fill=fill, line=edge, rounded=True)
        add_textbox(
            slide, left + Inches(0.3), Inches(4.2),
            box_w - Inches(0.6), Inches(0.5),
            title, font_size=20, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, left + Inches(0.3), Inches(4.85),
            box_w - Inches(0.6), Inches(1.5),
            body, font_size=13, color=TXT_BODY,
        )

    add_footer(slide, page, total)


def slide_guiding_principles(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "Three guiding principles", eyebrow="What we optimized for")

    principles = [
        ("Strict tenant isolation",
         "No tenant ever sees another tenant's data. Tenant scoping is "
         "applied at the data layer, not bolted onto controllers.",
         "1"),
        ("Cheapest path handles the dominant case",
         "The fastest, most reliable, lowest-cost code path serves the "
         "majority of traffic. AI is reserved for moments where it adds "
         "real value.",
         "2"),
        ("Auditable by default",
         "Every routing decision and AI invocation is logged. We can "
         "explain after the fact what the system did and why.",
         "3"),
    ]

    top = Inches(2.5)
    row_h = Inches(1.3)
    for i, (title, body, num) in enumerate(principles):
        y = top + row_h * i

        # Number circle
        circle = add_rect(
            slide, LEFT_MARGIN, y, Inches(0.85), Inches(0.85),
            fill=ACCENT_BLUE, rounded=True,
        )
        circle.adjustments[0] = 0.5  # max round corners
        add_textbox(
            slide, LEFT_MARGIN, y,
            Inches(0.85), Inches(0.85),
            num, font_size=28, color=BG_WHITE, bold=True,
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
        )

        add_textbox(
            slide, LEFT_MARGIN + Inches(1.15), y - Inches(0.05),
            Inches(11), Inches(0.5),
            title, font_size=20, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, LEFT_MARGIN + Inches(1.15), y + Inches(0.4),
            Inches(11), Inches(0.9),
            body, font_size=14, color=TXT_BODY,
        )

    add_footer(slide, page, total)


def slide_diagram(prs, page, total, diagram_path: Path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "System architecture, end to end", eyebrow="The big picture")

    if diagram_path.exists():
        # Center the image, scaled to fit
        img_w = Inches(11.0)
        left = (SLIDE_W - img_w) / 2
        slide.shapes.add_picture(
            str(diagram_path),
            left, Inches(1.85),
            width=img_w,
        )
    else:
        add_textbox(
            slide, LEFT_MARGIN, Inches(3),
            CONTENT_WIDTH, Inches(0.5),
            f"[Diagram missing: {diagram_path}]",
            font_size=14, color=TXT_LIGHT, align=PP_ALIGN.CENTER,
        )

    add_textbox(
        slide, LEFT_MARGIN, Inches(6.4),
        CONTENT_WIDTH, Inches(0.5),
        "Five layers — channels, application core, agents, the hybrid intent "
        "stack, data + integrations. Solid arrows = primary request flow; "
        "dashed = background work.",
        font_size=11, color=TXT_MUTE, italic=True, align=PP_ALIGN.CENTER,
    )

    add_footer(slide, page, total)


def slide_five_layers(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "The five layers, in one sentence each",
              eyebrow="Reading the diagram")

    rows = [
        ("EXTERNAL CHANNELS",
         "Volunteers via SMS, admins via web + SMS, super-admins via web.",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("APPLICATION CORE",
         "Web API, inbound webhook, scheduler, and observability — the "
         "FastAPI services that own the request loop.",
         CALLOUT_WARM, ACCENT_WARM),
        ("AGENT LAYER",
         "The Orchestrator routes to specialized agents: Engagement, "
         "Recruiter + Scheduler, Marketing, Review + Recognition.",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("HYBRID INTENT STACK",
         "Pattern rules → small AI classifier → full AI. Cross-cuts every "
         "inbound message.",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
        ("DATA & INTEGRATIONS",
         "PostgreSQL with row-level tenant isolation; Twilio, Anthropic, "
         "Google, Resend wrapped behind soft-fail boundaries.",
         CALLOUT_PEACH, ACCENT_PEACH),
    ]

    top = Inches(2.0)
    row_h = Inches(0.95)
    for i, (label, body, fill, edge) in enumerate(rows):
        y = top + row_h * i

        # Label chip on the left
        chip_w = Inches(2.8)
        add_rect(slide, LEFT_MARGIN, y, chip_w, Inches(0.7),
                 fill=fill, line=edge, rounded=True)
        add_textbox(
            slide, LEFT_MARGIN, y,
            chip_w, Inches(0.7),
            label, font_size=11, color=TXT_DARK, bold=True,
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
        )

        # Description to the right
        add_textbox(
            slide, LEFT_MARGIN + chip_w + Inches(0.3),
            y + Inches(0.1),
            Inches(9), Inches(0.6),
            body, font_size=14, color=TXT_BODY,
            anchor=MSO_ANCHOR.MIDDLE,
        )

    add_footer(slide, page, total)


def slide_pattern_block(prs, page, total, *, eyebrow: str, title: str,
                        what: str, why: str, benefit: str,
                        accent: RGBColor, callout: RGBColor):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, title, eyebrow=eyebrow)

    # Three labeled paragraphs with colored leading labels
    labels = [
        ("WHAT IT IS", what),
        ("WHY WE CHOSE IT", why),
        ("BUSINESS BENEFIT", benefit),
    ]
    y = Inches(2.05)
    for label, body in labels:
        # Accent strip
        add_rect(slide, LEFT_MARGIN, y + Inches(0.05),
                 Inches(0.12), Inches(1.3),
                 fill=accent, rounded=False)

        add_textbox(
            slide, LEFT_MARGIN + Inches(0.35), y,
            Inches(11.5), Inches(0.35),
            label, font_size=10, color=accent, bold=True,
        )
        add_textbox(
            slide, LEFT_MARGIN + Inches(0.35), y + Inches(0.35),
            Inches(11.5), Inches(1.05),
            body, font_size=14, color=TXT_BODY,
        )
        y += Inches(1.55)

    add_footer(slide, page, total)


def slide_pattern_group(prs, page, total, *, eyebrow: str, title: str,
                        patterns: list[tuple[str, str]],
                        accent: RGBColor, callout: RGBColor):
    """A slide that summarizes 3-4 related patterns side-by-side."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, title, eyebrow=eyebrow)

    n = len(patterns)
    box_w = (CONTENT_WIDTH - Inches(0.3) * (n - 1)) / n
    gap = Inches(0.3)
    top = Inches(2.1)
    box_h = Inches(4.5)

    for i, (pname, pbody) in enumerate(patterns):
        left = LEFT_MARGIN + (box_w + gap) * i
        add_rect(slide, left, top, box_w, box_h,
                 fill=callout, line=accent, rounded=True)
        add_textbox(
            slide, left + Inches(0.25), top + Inches(0.3),
            box_w - Inches(0.5), Inches(0.9),
            pname, font_size=15, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, left + Inches(0.25), top + Inches(1.3),
            box_w - Inches(0.5), box_h - Inches(1.6),
            pbody, font_size=12, color=TXT_BODY,
        )

    add_footer(slide, page, total)


def slide_hybrid_stack(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "Hybrid intent stack",
              eyebrow="The differentiator")

    add_textbox(
        slide, LEFT_MARGIN, Inches(2.0),
        CONTENT_WIDTH, Inches(0.6),
        "Every inbound message passes through up to three tiers. Each tier "
        "only fires when the previous one cannot answer confidently.",
        font_size=14, color=TXT_BODY, italic=True,
    )

    # Three stacked tier rows with cost + latency
    tiers = [
        ("Tier 1", "Pattern rules",
         "Canonical phrases — HERE, DONE, switch to kitchen.",
         "~5 ms", "$0", "~80–90% of messages",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("Tier 2", "Small AI classifier (Haiku)",
         'Long-tail phrasings — "im finally here lol", "leaving now".',
         "~300 ms", "~$0.0001", "~5–10% of messages",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
        ("Tier 3", "Full AI with tools",
         "Open questions and multi-turn conversations.",
         "~1–2 sec", "~$0.005–0.015", "Long tail",
         CALLOUT_BLUE, ACCENT_BLUE),
    ]

    top = Inches(2.8)
    row_h = Inches(1.2)
    for i, (tier, name, desc, latency, cost, share, fill, edge) in enumerate(tiers):
        y = top + row_h * i
        add_rect(slide, LEFT_MARGIN, y, CONTENT_WIDTH, Inches(1.05),
                 fill=fill, line=edge, rounded=True)

        # Tier label
        add_textbox(
            slide, LEFT_MARGIN + Inches(0.3), y + Inches(0.1),
            Inches(1.3), Inches(0.4),
            tier.upper(), font_size=10, color=edge, bold=True,
        )
        # Name
        add_textbox(
            slide, LEFT_MARGIN + Inches(0.3), y + Inches(0.4),
            Inches(4.5), Inches(0.6),
            name, font_size=17, color=TXT_DARK, bold=True,
        )
        # Description
        add_textbox(
            slide, LEFT_MARGIN + Inches(5.0), y + Inches(0.18),
            Inches(4.5), Inches(0.7),
            desc, font_size=12, color=TXT_BODY, italic=True,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        # Metrics column
        metrics_left = LEFT_MARGIN + Inches(9.6)
        add_textbox(
            slide, metrics_left, y + Inches(0.05),
            Inches(2.3), Inches(0.3),
            f"⏱  {latency}   💲 {cost}",
            font_size=11, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, metrics_left, y + Inches(0.45),
            Inches(2.3), Inches(0.5),
            share, font_size=10.5, color=TXT_MUTE, italic=True,
        )

    # Bottom takeaway
    add_textbox(
        slide, LEFT_MARGIN, Inches(6.45),
        CONTENT_WIDTH, Inches(0.5),
        "Average AI cost is dominated by Tier 1 (free). Check-in and check-out "
        "are 100% deterministic.",
        font_size=12, color=TXT_DARK, bold=True, align=PP_ALIGN.CENTER,
    )

    add_footer(slide, page, total)


def slide_cost_story(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "Cost-tiered AI: the headline economic point",
              eyebrow="Why this architecture matters")

    add_textbox(
        slide, LEFT_MARGIN, Inches(2.0),
        CONTENT_WIDTH, Inches(0.7),
        "Operating cost grows with message complexity, not with message "
        "volume. This decouples our AI spend from raw tenant growth.",
        font_size=15, color=TXT_BODY, italic=True,
    )

    # Two columns: "AI-only" vs "Our hybrid"
    col_w = Inches(5.8)
    gap = Inches(0.3)
    col_top = Inches(3.05)
    col_h = Inches(3.6)

    # Left column — AI-only world
    add_rect(slide, LEFT_MARGIN, col_top, col_w, col_h,
             fill=CALLOUT_PEACH, line=ACCENT_PEACH, rounded=True)
    add_textbox(
        slide, LEFT_MARGIN + Inches(0.3), col_top + Inches(0.25),
        col_w - Inches(0.6), Inches(0.45),
        "If we had gone AI-only", font_size=16, color=ACCENT_PEACH, bold=True,
    )
    add_bullet_list(
        slide,
        LEFT_MARGIN + Inches(0.3), col_top + Inches(0.85),
        col_w - Inches(0.6), col_h - Inches(1.0),
        [
            "Every check-in, ping, and reminder spends AI tokens.",
            "Cost scales with raw message volume — gross margin "
            "shrinks as tenants grow.",
            "Latency of 1–2 sec per message at peak times.",
            "Behavior shifts when the AI vendor changes models.",
        ],
        font_size=12, color=TXT_BODY,
    )

    # Right column — Our hybrid
    add_rect(slide, LEFT_MARGIN + col_w + gap, col_top, col_w, col_h,
             fill=CALLOUT_SAGE, line=ACCENT_SAGE, rounded=True)
    add_textbox(
        slide, LEFT_MARGIN + col_w + gap + Inches(0.3),
        col_top + Inches(0.25),
        col_w - Inches(0.6), Inches(0.45),
        "What we built instead",
        font_size=16, color=ACCENT_SAGE, bold=True,
    )
    add_bullet_list(
        slide,
        LEFT_MARGIN + col_w + gap + Inches(0.3),
        col_top + Inches(0.85),
        col_w - Inches(0.6), col_h - Inches(1.0),
        [
            "80–90% of messages handled deterministically — $0.",
            "Tenant growth does not pull AI cost with it.",
            "Sub-second response on the dominant case.",
            "Mission-critical actions are stable across model upgrades.",
        ],
        font_size=12, color=TXT_BODY,
    )

    add_footer(slide, page, total)


def slide_strategic_concerns(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "Strategic concerns the architecture addresses",
              eyebrow="Why it matters at the board level")

    concerns = [
        ("Margin protection at scale",
         "Cost grows with message complexity, not raw volume. The more "
         "successful a tenant becomes, the more our deterministic tier "
         "carries — not our AI budget.",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("Operational trust",
         "Volunteers and admins rely on the system at high-stakes "
         "moments. The architecture is tilted toward reliability — "
         "soft-fail dependencies, deterministic critical paths, full "
         "audit trail.",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("Optionality",
         "Adding a new agent, swapping an AI vendor, or supporting a "
         "new SMS provider is a contained refactor — not a platform "
         "rewrite. Future product bets stay cheap.",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
    ]

    box_w = Inches(3.85)
    gap = Inches(0.25)
    start_left = LEFT_MARGIN + Inches(0.05)
    for i, (title, body, fill, edge) in enumerate(concerns):
        left = start_left + (box_w + gap) * i
        add_rect(slide, left, Inches(2.3), box_w, Inches(4.2),
                 fill=fill, line=edge, rounded=True)
        add_textbox(
            slide, left + Inches(0.3), Inches(2.55),
            box_w - Inches(0.6), Inches(0.9),
            title, font_size=18, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, left + Inches(0.3), Inches(3.5),
            box_w - Inches(0.6), Inches(3.0),
            body, font_size=13, color=TXT_BODY,
        )

    add_footer(slide, page, total)


def slide_roadmap(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "What this architecture sets us up to do next",
              eyebrow="Roadmap")

    add_textbox(
        slide, LEFT_MARGIN, Inches(2.0),
        CONTENT_WIDTH, Inches(0.6),
        "Each item below is a contained extension — not a rewrite. The "
        "agent layer, configuration surface, and soft-fail dependencies "
        "make future changes cheap.",
        font_size=14, color=TXT_BODY, italic=True,
    )

    items = [
        ("Donations & Marketing Agent",
         "Public donation page + pluggable payment processors."),
        ("Semantic search",
         "pgvector + Voyage AI embeddings for conversation recall and "
         "similar-past-event suggestions."),
        ("Pluggable contact data",
         "External CRM, HRIS, or identity provider as source of truth "
         "for volunteer profiles."),
        ("AI agent surface (MCP)",
         "External AI tools can integrate with the platform via the "
         "Model Context Protocol."),
        ("Twilio sub-accounts",
         "Per-tenant SMS isolation, billing attribution, 10DLC "
         "registration."),
        ("Issue reporting pipeline",
         "Classifies user-reported problems to the right inbox — "
         "tenant admin or platform."),
    ]

    # Two columns of three
    col_w = Inches(5.9)
    col_gap = Inches(0.2)
    row_h = Inches(1.15)
    top = Inches(3.0)
    for i, (label, body) in enumerate(items):
        col = i % 2
        row = i // 2
        left = LEFT_MARGIN + (col_w + col_gap) * col
        y = top + row_h * row

        # Bullet dot
        add_rect(slide, left, y + Inches(0.25), Inches(0.15), Inches(0.15),
                 fill=ACCENT_BLUE, rounded=True)
        add_textbox(
            slide, left + Inches(0.35), y - Inches(0.05),
            col_w - Inches(0.5), Inches(0.4),
            label, font_size=14, color=TXT_DARK, bold=True,
        )
        add_textbox(
            slide, left + Inches(0.35), y + Inches(0.3),
            col_w - Inches(0.5), Inches(0.8),
            body, font_size=11, color=TXT_BODY,
        )

    add_footer(slide, page, total)


def slide_bottom_line(prs, page, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect(slide, Inches(0), Inches(0), Inches(0.35), SLIDE_H,
             fill=ACCENT_BLUE, rounded=False)

    add_textbox(
        slide, Inches(1.0), Inches(1.8),
        Inches(11.3), Inches(0.5),
        "BOTTOM LINE", font_size=12, color=ACCENT_BLUE, bold=True,
    )
    add_textbox(
        slide, Inches(1.0), Inches(2.3),
        Inches(11.3), Inches(1.1),
        "AI as a tool, not as a magic wand.",
        font_size=36, color=TXT_DARK, bold=True,
    )
    add_textbox(
        slide, Inches(1.0), Inches(3.6),
        Inches(11.3), Inches(2.5),
        "We built a platform where the cheapest, fastest, most reliable "
        "tier handles the largest share of traffic, and AI is reserved "
        "for moments where it adds real value.\n\n"
        "That's what lets us scale tenants without scaling cost, defend "
        "gross margin in an AI-priced market, and ship new product surfaces "
        "without rewriting what already works.",
        font_size=16, color=TXT_BODY,
    )

    add_textbox(
        slide, Inches(1.0), Inches(6.7),
        Inches(11.3), Inches(0.4),
        "Questions?", font_size=14, color=TXT_LIGHT, italic=True,
    )


# ── Build ──────────────────────────────────────────────────────────

def build(out_path: Path, diagram_path: Path) -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # Plan: 13 slides total
    total = 13

    slide_title(prs)                                               # 1
    slide_what_we_built(prs, 2, total)                             # 2
    slide_guiding_principles(prs, 3, total)                        # 3
    slide_diagram(prs, 4, total, diagram_path)                     # 4
    slide_five_layers(prs, 5, total)                               # 5

    # Patterns — three flagship ones get their own slide.
    slide_pattern_block(
        prs, 6, total,
        eyebrow="Pattern 1",
        title="Multi-tenant row-level isolation",
        what="Every record carries the tenant it belongs to. Every database "
             "query automatically scopes to that tenant. No shared data, "
             "no shared credentials, no shared prompts.",
        why="The strongest tenant boundary at the lowest operating cost. "
            "Faster onboarding, schema changes deploy once, cloud bill stays "
            "flat as tenants grow. Tenant scoping is enforced at the "
            "base-query layer so no developer can accidentally leak.",
        benefit="Minutes-to-onboard new tenants. Per-tenant credentials, "
                "prompts, and feature flags. Marginal cost per tenant "
                "dominated by usage, not infrastructure.",
        accent=ACCENT_BLUE, callout=CALLOUT_BLUE,
    )

    slide_pattern_block(
        prs, 7, total,
        eyebrow="Pattern 2",
        title="Path-A agent architecture",
        what="The AI-driven parts of the system are organized into four "
             "specialized agents — Orchestrator, Engagement, Recruiter + "
             "Scheduler, Marketing — each following the same internal shape.",
        why="Without this structure, AI features sprawl into a single "
            "overgrown handler that is hard to test, debug, or modify. The "
            "agent shape separates deciding what to do from doing it from "
            "explaining what was done. New agents drop into the same slot.",
        benefit="Faster feature delivery, lower regression risk, easier "
                "engineer onboarding. The agent boundary is also where we "
                "attribute AI cost and observability.",
        accent=ACCENT_SAGE, callout=CALLOUT_SAGE,
    )

    slide_hybrid_stack(prs, 8, total)                              # 8

    # The remaining 7 patterns grouped onto two slides
    slide_pattern_group(
        prs, 9, total,
        eyebrow="Operational reliability",
        title="Patterns for trust and uptime",
        patterns=[
            ("Webhook buffer",
             "Acknowledge inbound SMS in ~30 ms; process in the "
             "background. Carrier-side timeouts no longer become "
             "duplicate check-ins or lost messages."),
            ("Graceful degradation",
             "Every external dependency — Twilio, Anthropic, Google, "
             "Resend — wrapped in a soft-fail boundary. A vendor "
             "outage degrades one capability, not the whole product."),
            ("Optimistic concurrency",
             "Hot rows like pending service-change approvals use "
             "version numbers. Admins and volunteers can act in "
             "parallel; collisions resolve with a clean retry."),
            ("Graph-shaped audit",
             "Every routing decision, AI invocation, and tool call "
             "is logged with its relationships. We can answer 'why "
             "did the system do that?' for any message."),
        ],
        accent=ACCENT_PEACH, callout=CALLOUT_PEACH,
    )

    slide_pattern_group(
        prs, 10, total,
        eyebrow="Velocity & customization",
        title="Patterns for shipping and tuning",
        patterns=[
            ("Domain-driven folders",
             "Backend and frontend organized by business domain "
             "(bookings, recruitment, recognition, etc.). A feature "
             "change is a self-contained, reviewable unit."),
            ("Per-tenant configuration",
             "Prompts, feature flags, credentials, recognition "
             "definitions all live in a tenant-scoped config "
             "surface. Tenants self-customize without engineering."),
            ("Two-sided LLM personas",
             "Separate AI personas for volunteers and admins, with "
             "different tools and prompts. Customers never see "
             "admin operations and vice versa — smaller attack "
             "surface, clearer tool semantics."),
        ],
        accent=ACCENT_WARM, callout=CALLOUT_WARM,
    )

    slide_cost_story(prs, 11, total)                               # 11
    slide_strategic_concerns(prs, 12, total)                       # 12
    slide_roadmap(prs, 13, total)                                  # 13
    slide_bottom_line(prs, 14, total)                              # final / no footer

    prs.save(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    here = Path(__file__).parent
    build(
        out_path=here / "architecture_brief.pptx",
        diagram_path=here / "architecture_diagram.png",
    )


if __name__ == "__main__":
    main()
