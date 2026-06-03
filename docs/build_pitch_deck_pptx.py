"""Generate mustr_pitch_deck.pptx — investor-style pitch deck.

Covers problem → solution → product (today & tomorrow) → why now →
market → competition & gap → architecture moat → GTM →
tiered pricing → roadmap → ask.

Run: python docs/build_pitch_deck_pptx.py
Inputs:
  docs/architecture_diagram.png
  docs/pitch_competition_quadrant.png
  docs/pitch_market_sizing.png
  docs/pitch_roadmap_timeline.png
Output: docs/mustr_pitch_deck.pptx
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


# ── Geometry ──
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
TITLE_TOP = Inches(0.45)
TITLE_HEIGHT = Inches(0.85)
LEFT_MARGIN = Inches(0.7)
RIGHT_MARGIN = Inches(0.7)
CONTENT_WIDTH = SLIDE_W - LEFT_MARGIN - RIGHT_MARGIN
FOOTER_TOP = Inches(7.05)


# ── Helpers ────────────────────────────────────────────────────────

def add_textbox(slide, left, top, width, height, text, *,
                font_size=14, color=TXT_BODY, bold=False, italic=False,
                align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
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


def add_bullets(slide, left, top, width, height, items, *,
                font_size=14, color=TXT_BODY, line_spacing=1.25,
                space_before=8):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
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
            p.space_before = Pt(space_before)
    return box


def add_rect(slide, left, top, width, height, *, fill,
             line=None, rounded=True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
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
        1, LEFT_MARGIN, Inches(top),
        SLIDE_W - RIGHT_MARGIN, Inches(top),
    )
    line.line.color.rgb = DIVIDER
    line.line.width = Pt(0.75)


def add_title(slide, title, eyebrow=None):
    if eyebrow:
        add_textbox(slide, LEFT_MARGIN, TITLE_TOP - Inches(0.05),
                    CONTENT_WIDTH, Inches(0.3),
                    eyebrow.upper(),
                    font_size=10, color=ACCENT_BLUE, bold=True)
        add_textbox(slide, LEFT_MARGIN, TITLE_TOP + Inches(0.25),
                    CONTENT_WIDTH, TITLE_HEIGHT,
                    title, font_size=28, color=TXT_DARK, bold=True)
        add_divider(slide, 1.65)
    else:
        add_textbox(slide, LEFT_MARGIN, TITLE_TOP,
                    CONTENT_WIDTH, TITLE_HEIGHT,
                    title, font_size=28, color=TXT_DARK, bold=True)
        add_divider(slide, 1.45)


def add_footer(slide, page, total):
    add_textbox(slide, LEFT_MARGIN, FOOTER_TOP, CONTENT_WIDTH, Inches(0.3),
                "mustr  ·  Volunteer ops on autopilot",
                font_size=9, color=TXT_LIGHT, align=PP_ALIGN.LEFT)
    add_textbox(slide, LEFT_MARGIN, FOOTER_TOP, CONTENT_WIDTH, Inches(0.3),
                f"{page} / {total}",
                font_size=9, color=TXT_LIGHT, align=PP_ALIGN.RIGHT)


# ── Slide builders ─────────────────────────────────────────────────

def s_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect(s, Inches(0), Inches(0), Inches(0.35), SLIDE_H,
             fill=ACCENT_BLUE, rounded=False)
    add_textbox(s, Inches(1.0), Inches(2.0),
                Inches(11.3), Inches(0.5),
                "PITCH DECK", font_size=12, color=ACCENT_BLUE, bold=True)
    add_textbox(s, Inches(1.0), Inches(2.5),
                Inches(11.3), Inches(2.0),
                "mustr", font_size=72, color=TXT_DARK, bold=True)
    add_textbox(s, Inches(1.0), Inches(4.4),
                Inches(11.3), Inches(0.8),
                "An autonomous agent that runs your volunteer program — by SMS today, by voice next.",
                font_size=20, color=TXT_MUTE, italic=True)
    add_textbox(s, Inches(1.0), Inches(6.7),
                Inches(11.3), Inches(0.4),
                "Series Seed  ·  Confidential  ·  June 2026",
                font_size=11, color=TXT_LIGHT)


def s_problem(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Volunteer coordinators are drowning.",
              eyebrow="The problem")

    add_textbox(s, LEFT_MARGIN, Inches(2.05), CONTENT_WIDTH, Inches(0.7),
                "The work is repetitive. The tools are passive. The volunteers slip away.",
                font_size=17, color=TXT_BODY, italic=True)

    stats = [
        ("60–80%", "of a coordinator's time goes to scheduling, reminders, and chasing no-shows — not to running their mission."),
        ("33%", "drop in active US volunteers vs. pre-2020 (BLS). Coordinators must recruit harder for the same headcount."),
        ("28%", "average no-show rate at recurring events. Every no-show is a phone call, a panicked back-fill, or a missed shift."),
        ("$0", "spent by competitors on reaching out. Their tools wait for volunteers to act. Volunteers stop acting."),
    ]
    top = Inches(3.05)
    box_w = Inches(2.85)
    gap = Inches(0.20)
    start_left = LEFT_MARGIN
    for i, (num, body) in enumerate(stats):
        left = start_left + (box_w + gap) * i
        add_rect(s, left, top, box_w, Inches(3.1),
                 fill=CALLOUT_PEACH, line=ACCENT_PEACH, rounded=True)
        add_textbox(s, left + Inches(0.25), top + Inches(0.25),
                    box_w - Inches(0.5), Inches(1.0),
                    num, font_size=36, color=ACCENT_PEACH, bold=True)
        add_textbox(s, left + Inches(0.25), top + Inches(1.35),
                    box_w - Inches(0.5), Inches(1.6),
                    body, font_size=11.5, color=TXT_BODY)

    add_footer(s, s_idx, total)


def s_status_quo(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "What 2026 volunteer software still looks like",
              eyebrow="The status quo")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.6),
                "All of today's tools are admin dashboards. None of them reach out to volunteers on their own.",
                font_size=15, color=TXT_BODY, italic=True)

    rows = [
        ("Web sign-up forms", "Volunteer must visit, log in, click a slot. No outreach.",
         "SignUpGenius, VolunteerLocal"),
        ("CRM-style platforms", "Volunteer profile + event schedule. Admin still works the phones.",
         "Bloomerang Volunteer, Better Impact, Galaxy Digital"),
        ("Group chat sprawl", "WhatsApp, GroupMe, Discord. No structure, no compliance, no reporting.",
         "Ad-hoc adoption everywhere"),
        ("Spreadsheets + email blasts", "Free, manual, brittle. Default fallback for under-resourced orgs.",
         "Google Sheets + Mailchimp"),
        ("Call-center stacks", "Built for enterprise CX teams. $100K+ implementations.",
         "Five9, Twilio Flex, Genesys"),
    ]
    top = Inches(2.85)
    row_h = Inches(0.78)
    for i, (label, body, examples) in enumerate(rows):
        y = top + row_h * i
        add_rect(s, LEFT_MARGIN, y, Inches(3.2), Inches(0.65),
                 fill=CALLOUT_WARM, line=ACCENT_WARM, rounded=True)
        add_textbox(s, LEFT_MARGIN, y, Inches(3.2), Inches(0.65),
                    label, font_size=12, color=TXT_DARK, bold=True,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        add_textbox(s, LEFT_MARGIN + Inches(3.5), y + Inches(0.05),
                    Inches(6.4), Inches(0.6),
                    body, font_size=12, color=TXT_BODY,
                    anchor=MSO_ANCHOR.MIDDLE)
        add_textbox(s, LEFT_MARGIN + Inches(10.0), y + Inches(0.05),
                    Inches(2.0), Inches(0.6),
                    examples, font_size=10, color=TXT_LIGHT, italic=True,
                    anchor=MSO_ANCHOR.MIDDLE)

    add_footer(s, s_idx, total)


def s_solution(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "An autonomous agent that runs your volunteer program.",
              eyebrow="The solution")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.7),
                "Volunteers interact entirely by text (and soon voice). "
                "Coordinators move from doing the work to supervising it.",
                font_size=16, color=TXT_BODY, italic=True)

    capabilities = [
        ("Recruits", "Picks the right volunteers per event and reaches out in waves."),
        ("Schedules", "Books, confirms, handles reschedules, sends calendar invites."),
        ("Reminds", "Personalized nudges before each event — no spam, no opt-out churn."),
        ("Checks in & out", "Volunteers text 'HERE' / 'DONE'. Admin sees live roster in real time."),
        ("Recognizes", "Tracks hours, grants milestones and badges, surfaces top performers."),
        ("Reports", "Daily SMS update to the admin — what's filled, what's at risk, what to act on."),
    ]
    box_w = Inches(3.95)
    box_h = Inches(1.65)
    gap_x = Inches(0.13)
    gap_y = Inches(0.15)
    start_left = LEFT_MARGIN
    top = Inches(3.05)
    for i, (cap, body) in enumerate(capabilities):
        col = i % 3
        row = i // 3
        left = start_left + (box_w + gap_x) * col
        y = top + (box_h + gap_y) * row
        add_rect(s, left, y, box_w, box_h,
                 fill=CALLOUT_BLUE, line=ACCENT_BLUE, rounded=True)
        add_textbox(s, left + Inches(0.25), y + Inches(0.2),
                    box_w - Inches(0.5), Inches(0.4),
                    cap, font_size=16, color=ACCENT_BLUE, bold=True)
        add_textbox(s, left + Inches(0.25), y + Inches(0.7),
                    box_w - Inches(0.5), box_h - Inches(0.85),
                    body, font_size=11.5, color=TXT_BODY)

    add_footer(s, s_idx, total)


def s_voice_next(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Voice arrives next — same agent, new channel.",
              eyebrow="Tomorrow")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.7),
                "SMS reaches the volunteers who text. Voice reaches everyone else — "
                "and unlocks higher-fidelity moments that text can't.",
                font_size=15, color=TXT_BODY, italic=True)

    # Two columns: SMS today vs Voice next
    col_w = Inches(5.95)
    gap = Inches(0.25)
    top = Inches(3.0)
    col_h = Inches(3.7)

    # SMS today
    add_rect(s, LEFT_MARGIN, top, col_w, col_h,
             fill=CALLOUT_BLUE, line=ACCENT_BLUE, rounded=True)
    add_textbox(s, LEFT_MARGIN + Inches(0.3), top + Inches(0.25),
                col_w - Inches(0.6), Inches(0.5),
                "SMS Agent — shipping today",
                font_size=18, color=ACCENT_BLUE, bold=True)
    add_bullets(
        s,
        LEFT_MARGIN + Inches(0.3), top + Inches(0.9),
        col_w - Inches(0.6), col_h - Inches(1.1),
        [
            "Inbound + outbound text on tenant Twilio number.",
            "Free-form NLU: \"im running 5 min late\" works.",
            "Per-tenant prompts, brand voice, opt-out compliance.",
            "Reaches younger and screen-fluent volunteers.",
        ],
        font_size=12.5, color=TXT_BODY,
    )

    # Voice next
    add_rect(s, LEFT_MARGIN + col_w + gap, top, col_w, col_h,
             fill=CALLOUT_SAGE, line=ACCENT_SAGE, rounded=True)
    add_textbox(s, LEFT_MARGIN + col_w + gap + Inches(0.3),
                top + Inches(0.25),
                col_w - Inches(0.6), Inches(0.5),
                "Voice Agent — Q1 2027",
                font_size=18, color=ACCENT_SAGE, bold=True)
    add_bullets(
        s,
        LEFT_MARGIN + col_w + gap + Inches(0.3), top + Inches(0.9),
        col_w - Inches(0.6), col_h - Inches(1.1),
        [
            "Outbound confirmation calls — TCPA-compliant.",
            "Reaches older volunteers who don't reliably text.",
            "Real-time wellness checks for senior-volunteer programs.",
            "Inbound IVR replaced by natural conversation.",
            "Same agent brain — only the channel changes.",
        ],
        font_size=12.5, color=TXT_BODY,
    )

    add_footer(s, s_idx, total)


def s_why_now(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Four tailwinds converging at the same moment.",
              eyebrow="Why now")

    tailwinds = [
        ("AI cost has fallen 100× in 18 months",
         "Haiku-class models make a per-message AI tier economically viable "
         "for nonprofit budgets. Voice models (Whisper, ElevenLabs, Deepgram) "
         "cleared the latency bar in late 2025.",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("Post-COVID volunteer recovery is stalling",
         "Active volunteer counts are still ~33% below 2019. Coordinators "
         "feel the gap. Demand for 'more leverage per coordinator' is "
         "structurally higher than it was 3 years ago.",
         CALLOUT_PEACH, ACCENT_PEACH),
        ("SMS compliance has stabilized",
         "10DLC registration, opt-in / opt-out standards, and Twilio "
         "sub-account economics are now mature enough that a "
         "purpose-built SMS product can ship cleanly.",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("Voice AI just crossed the conversational bar",
         "Sub-300ms end-to-end response with natural prosody is finally "
         "real. Conversational TCPA-compliant outbound is a 2026 product, "
         "not a 2028 product.",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
    ]
    box_w = Inches(5.95)
    box_h = Inches(2.0)
    gap_x = Inches(0.2)
    gap_y = Inches(0.2)
    top = Inches(2.4)
    for i, (title, body, fill, edge) in enumerate(tailwinds):
        col = i % 2
        row = i // 2
        left = LEFT_MARGIN + (box_w + gap_x) * col
        y = top + (box_h + gap_y) * row
        add_rect(s, left, y, box_w, box_h, fill=fill, line=edge, rounded=True)
        add_textbox(s, left + Inches(0.3), y + Inches(0.25),
                    box_w - Inches(0.6), Inches(0.5),
                    title, font_size=15, color=TXT_DARK, bold=True)
        add_textbox(s, left + Inches(0.3), y + Inches(0.85),
                    box_w - Inches(0.6), box_h - Inches(1.0),
                    body, font_size=11.5, color=TXT_BODY)

    add_footer(s, s_idx, total)


def s_competition(s_idx, total, img_path):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Nobody is doing autonomous, multi-channel volunteer ops.",
              eyebrow="Competitive landscape")

    if img_path.exists():
        # Quadrant on left, takeaway on right
        s.shapes.add_picture(str(img_path), LEFT_MARGIN, Inches(1.95),
                             width=Inches(7.5))
    # Right-side takeaways
    right_left = LEFT_MARGIN + Inches(7.85)
    right_w = Inches(4.05)
    add_textbox(s, right_left, Inches(2.05), right_w, Inches(0.4),
                "THE GAP", font_size=11, color=ACCENT_BLUE, bold=True)
    add_textbox(s, right_left, Inches(2.5), right_w, Inches(0.8),
                "Everyone else built admin software.",
                font_size=20, color=TXT_DARK, bold=True)
    add_textbox(s, right_left, Inches(3.5), right_w, Inches(2.5),
                "We built a volunteer-facing agent that admins supervise. "
                "The market has no incumbent that's both autonomous AND "
                "multi-channel — that's the quadrant we own.",
                font_size=12, color=TXT_BODY)

    add_textbox(s, right_left, Inches(5.4), right_w, Inches(0.4),
                "WHY THEY HAVEN'T", font_size=11, color=ACCENT_BLUE, bold=True)
    add_bullets(
        s, right_left, Inches(5.8), right_w, Inches(1.0),
        [
            "Legacy code · CRM mindset.",
            "AI cost only became viable in 2025.",
            "Voice agents only got good in 2026.",
        ],
        font_size=11, color=TXT_BODY, space_before=4,
    )

    add_footer(s, s_idx, total)


def s_market(s_idx, total, img_path):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Market size", eyebrow="TAM / SAM / SOM")

    if img_path.exists():
        s.shapes.add_picture(str(img_path), LEFT_MARGIN, Inches(1.95),
                             width=Inches(11.95))

    add_textbox(s, LEFT_MARGIN, Inches(6.4), CONTENT_WIDTH, Inches(0.5),
                "Volunteer-mgmt software is small but underserved by AI. "
                "Adjacent expansions (donations, event ops) extend the addressable "
                "spend per tenant by ~3×.",
                font_size=11, color=TXT_MUTE, italic=True,
                align=PP_ALIGN.CENTER)

    add_footer(s, s_idx, total)


def s_architecture_moat(s_idx, total, img_path):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Why a generic AI assistant won't catch us.",
              eyebrow="Architecture moat")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.65),
                "We built a layered system that makes AI cheap, reliable, "
                "and auditable — not just plausible.",
                font_size=15, color=TXT_BODY, italic=True)

    # Left: condensed moat bullets. Right: small diagram preview.
    left_w = Inches(5.3)
    add_textbox(s, LEFT_MARGIN, Inches(2.9), left_w, Inches(0.4),
                "OUR MOAT", font_size=11, color=ACCENT_BLUE, bold=True)
    add_bullets(
        s, LEFT_MARGIN, Inches(3.35), left_w, Inches(3.5),
        [
            "Hybrid intent stack: rules → small AI → full AI. "
            "80–90% of messages cost $0.",
            "Multi-tenant from day one — onboarding in minutes, "
            "schema migrations apply once.",
            "Agent architecture: Engagement, Recruiter+Scheduler, "
            "Marketing — independently evolvable.",
            "Audit-by-default: every routing decision logged. "
            "Compliance-ready posture.",
            "Soft-fail external dependencies — Twilio / Anthropic / "
            "Google outages degrade, don't break.",
        ],
        font_size=12.5, color=TXT_BODY,
    )

    # Right: diagram thumbnail
    if img_path.exists():
        s.shapes.add_picture(str(img_path),
                             LEFT_MARGIN + Inches(6.0), Inches(2.5),
                             width=Inches(6.0))
        add_textbox(s, LEFT_MARGIN + Inches(6.0), Inches(6.4),
                    Inches(6.0), Inches(0.4),
                    "Full system architecture — see companion brief.",
                    font_size=9, color=TXT_LIGHT, italic=True,
                    align=PP_ALIGN.CENTER)

    add_footer(s, s_idx, total)


def s_pricing(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Tiered pricing — designed for nonprofit budgets.",
              eyebrow="Business model")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.55),
                "Free tier seeds adoption. Paid tiers scale with active volunteers "
                "and unlock the agent + the channels that drive ROI.",
                font_size=14, color=TXT_BODY, italic=True)

    tiers = [
        ("Starter", "Free",
         "<50 active vols",
         [
             "Inbound SMS",
             "Basic scheduling",
             "mustr branding on SMS",
             "Community support",
         ],
         "Lead-gen tier",
         CALLOUT_WARM, ACCENT_WARM),
        ("Growth", "$99 / mo",
         "Up to 250 vols",
         [
             "Full SMS Agent (engagement)",
             "Reminders & follow-up",
             "Recognition (basic)",
             "Email support",
         ],
         "Most SMB nonprofits",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("Pro", "$299 / mo",
         "Up to 1,000 vols",
         [
             "Recruiter Agent (autonomous fill)",
             "Multi-event + roster sharing",
             "Full recognition + analytics",
             "200 Voice minutes / mo *",
             "Priority support",
         ],
         "Growing nonprofits + federations",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("Enterprise", "from $999",
         "Unlimited vols",
         [
             "Full Voice Agent (with overage)",
             "SSO + custom integrations",
             "Pluggable CRM/HRIS adapters",
             "Dedicated CSM + SLA",
             "10DLC sub-account",
         ],
         "Denominations · staffing co's",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
    ]
    top = Inches(2.85)
    box_h = Inches(3.95)
    n = len(tiers)
    box_w = (CONTENT_WIDTH - Inches(0.15) * (n - 1)) / n
    gap = Inches(0.15)
    for i, (name, price, vols, features, segment, fill, edge) in enumerate(tiers):
        left = LEFT_MARGIN + (box_w + gap) * i
        add_rect(s, left, top, box_w, box_h, fill=fill, line=edge, rounded=True)
        add_textbox(s, left + Inches(0.2), top + Inches(0.2),
                    box_w - Inches(0.4), Inches(0.4),
                    name.upper(), font_size=12, color=edge, bold=True)
        add_textbox(s, left + Inches(0.2), top + Inches(0.55),
                    box_w - Inches(0.4), Inches(0.6),
                    price, font_size=24, color=TXT_DARK, bold=True)
        add_textbox(s, left + Inches(0.2), top + Inches(1.2),
                    box_w - Inches(0.4), Inches(0.3),
                    vols, font_size=10.5, color=TXT_MUTE, italic=True)
        # Features
        add_bullets(
            s, left + Inches(0.2), top + Inches(1.55),
            box_w - Inches(0.4), Inches(2.0),
            features, font_size=10.5, color=TXT_BODY,
            line_spacing=1.2, space_before=4,
        )
        # Segment tag
        add_textbox(s, left + Inches(0.2),
                    top + box_h - Inches(0.4),
                    box_w - Inches(0.4), Inches(0.3),
                    segment.upper(), font_size=9, color=edge, bold=True)

    # Footnote
    add_textbox(s, LEFT_MARGIN, FOOTER_TOP - Inches(0.25),
                CONTENT_WIDTH, Inches(0.3),
                "* Voice ships Q1 2027 (Beta) / Q2 2027 (GA). "
                "Overage: $0.07/min. SMS pass-through included up to tier cap; overages "
                "billed at $0.012 / message.",
                font_size=9, color=TXT_LIGHT, italic=True)

    add_footer(s, s_idx, total)


def s_unit_economics(s_idx, total):
    """The $99/mo defense slide. Shows usage assumptions, COGS line items,
    margin headline, and the AI-only counterfactual side-by-side."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "$99 / month works — here's the math.",
              eyebrow="Unit economics")

    add_textbox(
        s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.55),
        "A typical Growth-tier tenant: 250 active volunteers, "
        "~10 events / month, ~2,000 SMS / month.",
        font_size=14, color=TXT_BODY, italic=True,
    )

    # ── Top row: usage card + cost breakdown card ──
    top = Inches(2.85)
    card_h = Inches(2.55)
    card_w = Inches(5.95)
    gap = Inches(0.25)

    # Usage card (left)
    add_rect(s, LEFT_MARGIN, top, card_w, card_h,
             fill=CALLOUT_BLUE, line=ACCENT_BLUE, rounded=True)
    add_textbox(s, LEFT_MARGIN + Inches(0.3), top + Inches(0.2),
                card_w - Inches(0.6), Inches(0.35),
                "USAGE PER TENANT / MONTH",
                font_size=10.5, color=ACCENT_BLUE, bold=True)

    usage_rows = [
        ("Active volunteers", "≤ 250"),
        ("Events / month", "~10"),
        ("SMS messages (in + out)", "~2,000"),
        ("Tier 1 (regex)", "~85% of inbound → $0"),
        ("Tier 2 (Haiku classifier)", "~10% → ~$0.0001 each"),
        ("Tier 3 (full LLM)", "~5% → ~$0.036 each"),
    ]
    label_x = LEFT_MARGIN + Inches(0.3)
    val_x = LEFT_MARGIN + Inches(3.4)
    y0 = top + Inches(0.7)
    line_h = Inches(0.28)
    for i, (label, val) in enumerate(usage_rows):
        y = y0 + line_h * i
        add_textbox(s, label_x, y, Inches(3.1), Inches(0.3),
                    label, font_size=11, color=TXT_BODY)
        add_textbox(s, val_x, y, card_w - Inches(3.6), Inches(0.3),
                    val, font_size=11, color=TXT_DARK, bold=True)

    # Cost breakdown card (right)
    cost_left = LEFT_MARGIN + card_w + gap
    add_rect(s, cost_left, top, card_w, card_h,
             fill=CALLOUT_PEACH, line=ACCENT_PEACH, rounded=True)
    add_textbox(s, cost_left + Inches(0.3), top + Inches(0.2),
                card_w - Inches(0.6), Inches(0.35),
                "WHAT IT COSTS US / MONTH",
                font_size=10.5, color=ACCENT_PEACH, bold=True)

    cost_rows = [
        ("SMS pass-through (Twilio)", "$16"),
        ("AI inference (hybrid stack)", "$1"),
        ("Infrastructure (DB + compute)", "$5"),
        ("Support (batched, AI-assisted)", "$10"),
    ]
    y0 = top + Inches(0.7)
    for i, (label, val) in enumerate(cost_rows):
        y = y0 + line_h * i
        add_textbox(s, cost_left + Inches(0.3), y,
                    Inches(3.5), Inches(0.3),
                    label, font_size=11, color=TXT_BODY)
        add_textbox(s, cost_left + Inches(4.0), y,
                    Inches(1.5), Inches(0.3),
                    val, font_size=11, color=TXT_DARK, bold=True,
                    align=PP_ALIGN.RIGHT)

    # Total row with divider
    total_y = top + Inches(1.9)
    sep = s.shapes.add_connector(
        1,
        cost_left + Inches(0.3), total_y,
        cost_left + card_w - Inches(0.3), total_y,
    )
    sep.line.color.rgb = ACCENT_PEACH
    sep.line.width = Pt(0.75)
    add_textbox(s, cost_left + Inches(0.3), total_y + Inches(0.1),
                Inches(3.5), Inches(0.4),
                "TOTAL COGS", font_size=12,
                color=ACCENT_PEACH, bold=True)
    add_textbox(s, cost_left + Inches(4.0), total_y + Inches(0.05),
                Inches(1.5), Inches(0.4),
                "$32", font_size=20, color=TXT_DARK, bold=True,
                align=PP_ALIGN.RIGHT)

    # ── Bottom row: margin headline + counterfactual ──
    bottom_top = top + card_h + Inches(0.2)
    bottom_h = Inches(1.55)

    # Margin headline (left)
    margin_w = Inches(7.7)
    add_rect(s, LEFT_MARGIN, bottom_top, margin_w, bottom_h,
             fill=CALLOUT_SAGE, line=ACCENT_SAGE, rounded=True)
    add_textbox(s, LEFT_MARGIN + Inches(0.4), bottom_top + Inches(0.2),
                margin_w - Inches(0.8), Inches(0.4),
                "GROSS MARGIN AT $99 / MO",
                font_size=11, color=ACCENT_SAGE, bold=True)
    add_textbox(s, LEFT_MARGIN + Inches(0.4), bottom_top + Inches(0.55),
                Inches(3.5), Inches(0.95),
                "$67 / mo  ·  68%",
                font_size=34, color=TXT_DARK, bold=True)
    add_textbox(s, LEFT_MARGIN + Inches(4.0), bottom_top + Inches(0.55),
                margin_w - Inches(4.4), Inches(0.95),
                "Healthy SaaS-class margin while keeping the price "
                "where SMB nonprofits can buy without procurement.",
                font_size=11, color=TXT_BODY, italic=True,
                anchor=MSO_ANCHOR.MIDDLE)

    # Counterfactual (right)
    cf_left = LEFT_MARGIN + margin_w + Inches(0.25)
    cf_w = CONTENT_WIDTH - margin_w - Inches(0.25)
    add_rect(s, cf_left, bottom_top, cf_w, bottom_h,
             fill=RGBColor(0xF5, 0xF5, 0xF5),
             line=RGBColor(0xCC, 0xCC, 0xCC), rounded=True)
    add_textbox(s, cf_left + Inches(0.25), bottom_top + Inches(0.15),
                cf_w - Inches(0.5), Inches(0.3),
                "AI-ONLY ARCHITECTURE",
                font_size=9.5, color=TXT_MUTE, bold=True)
    add_textbox(s, cf_left + Inches(0.25), bottom_top + Inches(0.45),
                cf_w - Inches(0.5), Inches(0.4),
                "$67 COGS  →  32% margin",
                font_size=15, color=TXT_DARK, bold=True)
    add_textbox(s, cf_left + Inches(0.25), bottom_top + Inches(0.9),
                cf_w - Inches(0.5), Inches(0.6),
                "Hybrid stack saves ~$35 / tenant / mo. "
                "At 1,000 paying tenants, that's ~$420K / yr in "
                "gross profit recovered by the architecture.",
                font_size=10, color=TXT_BODY, italic=True)

    # Footnote
    add_textbox(
        s, LEFT_MARGIN, FOOTER_TOP - Inches(0.25),
        CONTENT_WIDTH, Inches(0.3),
        "Assumes US 10DLC SMS at ~$0.008 / msg, Sonnet at $3 / MTok in + "
        "$15 / MTok out for Tier 3 (~$0.036 avg / call), Haiku at "
        "~$0.0001 / call for Tier 2. Pro tier ($299) holds ~50% margin "
        "at 4× usage including 200 voice minutes.",
        font_size=9, color=TXT_LIGHT, italic=True,
    )

    add_footer(s, s_idx, total)


def s_gtm(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Three motions, one funnel.",
              eyebrow="Go-to-market")

    add_textbox(s, LEFT_MARGIN, Inches(2.0), CONTENT_WIDTH, Inches(0.6),
                "Self-serve at the bottom, sales-assisted in the middle, "
                "partner-led at the top.",
                font_size=15, color=TXT_BODY, italic=True)

    motions = [
        ("Bottoms-up (PLG)",
         "Starter and Growth tiers, self-serve.",
         [
             "Inbound from community forums (NTEN, "
             "VolunteerMatch, faith ops Facebook groups).",
             "Free tier with mustr branding drives "
             "word-of-mouth from the volunteers themselves.",
             "Donation feature unlocks as the conversion hook.",
         ],
         "Goal: 1,000 free tenants by Q4 2026 → ~10% conversion to paid.",
         CALLOUT_BLUE, ACCENT_BLUE),
        ("Sales-assisted",
         "Pro tier, light-touch outbound.",
         [
             "SDR cohort targeting mid-size nonprofits and "
             "event-staffing agencies.",
             "Case-study driven: published 'we ran X's food drive' wins.",
             "Demo flow: 7-day pilot to first booked event.",
         ],
         "Goal: 200 Pro tenants by Q4 2026, ARR $700K.",
         CALLOUT_SAGE, ACCENT_SAGE),
        ("Partner-led",
         "Enterprise tier, multi-tenant deals.",
         [
             "Denominational HQs (10–500 churches each).",
             "Nonprofit federations (United Way, Catholic Charities).",
             "Event-staffing networks: one sale → many tenants.",
         ],
         "Goal: 10 partner deals by mid-2027, ~250 tenants captured.",
         CALLOUT_LAVENDER, ACCENT_LAVENDER),
    ]
    top = Inches(2.95)
    box_h = Inches(3.85)
    box_w = (CONTENT_WIDTH - Inches(0.2) * 2) / 3
    gap = Inches(0.2)
    for i, (name, sub, items, goal, fill, edge) in enumerate(motions):
        left = LEFT_MARGIN + (box_w + gap) * i
        add_rect(s, left, top, box_w, box_h, fill=fill, line=edge, rounded=True)
        add_textbox(s, left + Inches(0.25), top + Inches(0.2),
                    box_w - Inches(0.5), Inches(0.4),
                    name, font_size=16, color=edge, bold=True)
        add_textbox(s, left + Inches(0.25), top + Inches(0.7),
                    box_w - Inches(0.5), Inches(0.3),
                    sub, font_size=10.5, color=TXT_MUTE, italic=True)
        add_bullets(
            s, left + Inches(0.25), top + Inches(1.1),
            box_w - Inches(0.5), Inches(2.0),
            items, font_size=10.5, color=TXT_BODY,
            line_spacing=1.2, space_before=4,
        )
        # Goal callout at the bottom
        add_textbox(s, left + Inches(0.25),
                    top + box_h - Inches(0.65),
                    box_w - Inches(0.5), Inches(0.55),
                    goal, font_size=10, color=edge, bold=True, italic=True)

    add_footer(s, s_idx, total)


def s_roadmap(s_idx, total, img_path):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "What ships, when.", eyebrow="Roadmap")

    if img_path.exists():
        s.shapes.add_picture(str(img_path), LEFT_MARGIN, Inches(1.85),
                             width=Inches(11.95))

    add_textbox(s, LEFT_MARGIN, Inches(6.0), CONTENT_WIDTH, Inches(0.85),
                "Voice is the inflection. SMS gets us into the building; "
                "Voice triples our addressable channel reach and unlocks "
                "demographics SMS-only tools can't serve (older "
                "volunteers, wellness-check programs, low-literacy contexts).",
                font_size=12, color=TXT_BODY, italic=True,
                align=PP_ALIGN.CENTER)

    add_footer(s, s_idx, total)


def s_traction(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Where we are and what we need.",
              eyebrow="Traction & ask")

    # Two-column layout
    left_w = Inches(5.95)
    gap = Inches(0.25)
    top = Inches(2.05)
    col_h = Inches(4.7)

    # Where we are
    add_rect(s, LEFT_MARGIN, top, left_w, col_h,
             fill=CALLOUT_BLUE, line=ACCENT_BLUE, rounded=True)
    add_textbox(s, LEFT_MARGIN + Inches(0.3), top + Inches(0.25),
                left_w - Inches(0.6), Inches(0.5),
                "Where we are", font_size=18, color=ACCENT_BLUE, bold=True)
    add_bullets(
        s, LEFT_MARGIN + Inches(0.3), top + Inches(0.85),
        left_w - Inches(0.6), col_h - Inches(1.0),
        [
            "Platform shipped: 5-phase event lifecycle "
            "(check-in, check-out, mid-event SWITCH, post-event "
            "review, recognition).",
            "Multi-tenant architecture in production with row-level "
            "isolation and per-tenant credentials.",
            "Hybrid intent stack (regex → Haiku → full LLM) live.",
            "Pilot tenants: 3 active, ~600 volunteers under management.",
            "Token cost / message: trending below $0.001.",
        ],
        font_size=12, color=TXT_BODY, line_spacing=1.25,
    )

    # What we need
    add_rect(s, LEFT_MARGIN + left_w + gap, top, left_w, col_h,
             fill=CALLOUT_SAGE, line=ACCENT_SAGE, rounded=True)
    add_textbox(s, LEFT_MARGIN + left_w + gap + Inches(0.3),
                top + Inches(0.25),
                left_w - Inches(0.6), Inches(0.5),
                "What we need", font_size=18, color=ACCENT_SAGE, bold=True)

    add_textbox(s, LEFT_MARGIN + left_w + gap + Inches(0.3),
                top + Inches(0.95),
                left_w - Inches(0.6), Inches(0.6),
                "Series Seed — $2.5M", font_size=24, color=TXT_DARK, bold=True)

    add_textbox(s, LEFT_MARGIN + left_w + gap + Inches(0.3),
                top + Inches(1.65),
                left_w - Inches(0.6), Inches(0.4),
                "18-month runway to Voice GA + 500 paid tenants.",
                font_size=12, color=TXT_MUTE, italic=True)

    add_bullets(
        s, LEFT_MARGIN + left_w + gap + Inches(0.3),
        top + Inches(2.2), left_w - Inches(0.6), Inches(2.5),
        [
            "Voice engineering (~$700K, 4 hires).",
            "Sales + partnerships (~$900K, 3 hires).",
            "Compliance: 10DLC, TCPA, SOC 2 prep (~$300K).",
            "Working capital, infra, AI spend (~$600K).",
        ],
        font_size=11.5, color=TXT_BODY, line_spacing=1.25,
    )

    add_footer(s, s_idx, total)


def s_closing(s_idx, total):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect(s, Inches(0), Inches(0), Inches(0.35), SLIDE_H,
             fill=ACCENT_BLUE, rounded=False)

    add_textbox(s, Inches(1.0), Inches(1.8),
                Inches(11.3), Inches(0.5),
                "THE BOTTOM LINE", font_size=12,
                color=ACCENT_BLUE, bold=True)
    add_textbox(s, Inches(1.0), Inches(2.3),
                Inches(11.3), Inches(1.4),
                "An autopilot for volunteer ops.",
                font_size=44, color=TXT_DARK, bold=True)
    add_textbox(s, Inches(1.0), Inches(3.85),
                Inches(11.3), Inches(2.6),
                "SMS today, voice next, one agent across both.\n\n"
                "We're filling a quadrant the incumbents can't reach: "
                "autonomous, multi-channel volunteer ops at a price "
                "nonprofits can afford. The architecture is built for the "
                "next decade of AI-priced software — cheap where it can "
                "be, reliable where it must be, auditable everywhere.\n\n"
                "Let's run your next event together.",
                font_size=15, color=TXT_BODY)

    add_textbox(s, Inches(1.0), Inches(6.65),
                Inches(11.3), Inches(0.4),
                "Contact: founders@mustr.app  ·  mustr.app",
                font_size=12, color=TXT_LIGHT, italic=True)


# ── Build ──────────────────────────────────────────────────────────

# Module-level so slide builders can append to it
prs: Presentation


def build(out_path: Path, base: Path) -> None:
    global prs
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    arch_diagram = base / "architecture_diagram.png"
    competition = base / "pitch_competition_quadrant.png"
    market = base / "pitch_market_sizing.png"
    roadmap = base / "pitch_roadmap_timeline.png"

    total = 14

    s_title(prs)                             # 1 (no footer)
    s_problem(2, total)                      # 2
    s_status_quo(3, total)                   # 3
    s_solution(4, total)                     # 4
    s_voice_next(5, total)                   # 5
    s_why_now(6, total)                      # 6
    s_competition(7, total, competition)     # 7
    s_market(8, total, market)               # 8
    s_architecture_moat(9, total, arch_diagram)  # 9
    s_pricing(10, total)                     # 10
    s_unit_economics(11, total)              # 11 — NEW: $99 defense
    s_gtm(12, total)                         # 12
    s_roadmap(13, total, roadmap)            # 13
    s_traction(14, total)                    # 14
    s_closing(15, total)                     # 15 (no footer)

    prs.save(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    here = Path(__file__).parent
    build(here / "mustr_pitch_deck.pptx", here)


if __name__ == "__main__":
    main()
