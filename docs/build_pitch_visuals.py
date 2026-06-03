"""Generate visuals for the pitch deck.

Outputs:
  docs/pitch_competition_quadrant.png
  docs/pitch_market_sizing.png
  docs/pitch_roadmap_timeline.png

Run: python docs/build_pitch_visuals.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch


# Shared palette (matches the architecture deck)
ACCENT_BLUE = "#5B7AB8"
ACCENT_SAGE = "#7BA070"
ACCENT_PEACH = "#C58A6B"
ACCENT_LAVENDER = "#9474A6"
ACCENT_WARM = "#9C8F76"
INK = "#1A1A1A"
MUTE = "#555555"
LIGHT = "#888888"


# ── 1. Competitive landscape quadrant ─────────────────────────────

def build_competition(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))

    # Quadrant background tints
    ax.add_patch(plt.Rectangle((0, 0.5), 0.5, 0.5, color="#F5F5F5", zorder=0))
    ax.add_patch(plt.Rectangle((0.5, 0.5), 0.5, 0.5, color="#E8EEF7", alpha=0.6, zorder=0))
    ax.add_patch(plt.Rectangle((0, 0), 0.5, 0.5, color="#F0EBEB", alpha=0.4, zorder=0))
    ax.add_patch(plt.Rectangle((0.5, 0), 0.5, 0.5, color="#E4EDE3", alpha=0.5, zorder=0))

    # Quadrant labels — tuck them into corners so they never collide with bubbles
    ax.text(0.02, 0.97, "Wide reach, low automation",
            fontsize=10, color=MUTE, va="top", style="italic")
    ax.text(0.55, 0.97, "WHERE WE PLAY",
            fontsize=11, color=ACCENT_BLUE, ha="left", va="top", weight="bold")
    ax.text(0.02, 0.03, "Narrow & passive",
            fontsize=10, color=MUTE, va="bottom", style="italic")
    ax.text(0.98, 0.03, "Autonomous but single-channel",
            fontsize=10, color=MUTE, ha="right", va="bottom", style="italic")

    # Competitors
    competitors = [
        # name, x (autonomy), y (channel reach), color, size, label_offset
        ("SignUpGenius",      0.10, 0.20, ACCENT_WARM, 700, (0.04, 0.04)),
        ("VolunteerLocal",    0.18, 0.25, ACCENT_WARM, 700, (0.04, -0.05)),
        ("Better Impact",     0.22, 0.32, ACCENT_WARM, 800, (0.04, 0.03)),
        ("Bloomerang Vol.",   0.28, 0.30, ACCENT_WARM, 800, (0.04, -0.05)),
        ("Galaxy Digital",    0.20, 0.42, ACCENT_WARM, 700, (-0.18, 0.04)),
        ("WhatsApp groups",   0.05, 0.60, LIGHT,       650, (0.04, 0.03)),
        ("Spreadsheets +\nemail blasts", 0.05, 0.10, LIGHT, 600, (0.04, -0.03)),
        ("Call-center stacks\n(Five9 etc.)", 0.45, 0.55, LIGHT, 700, (0.04, 0.05)),
        ("DIY OpenAI /\nAnthropic builds", 0.80, 0.40, LIGHT, 700, (-0.27, -0.05)),
    ]
    for name, x, y, color, size, offset in competitors:
        ax.scatter(x, y, s=size, c=color, edgecolors="white", linewidths=2, zorder=3)
        ax.annotate(
            name, (x, y),
            xytext=(x + offset[0], y + offset[1]),
            fontsize=9, color=INK,
        )

    # Our position — today and tomorrow
    ax.scatter(0.72, 0.70, s=1100, c=ACCENT_BLUE, edgecolors="white", linewidths=3, zorder=5)
    ax.annotate("mustr (SMS\ntoday)", (0.72, 0.70),
                xytext=(0.76, 0.70), fontsize=11, color=ACCENT_BLUE,
                weight="bold", va="center")

    ax.scatter(0.93, 0.92, s=1500, c=ACCENT_SAGE, edgecolors="white", linewidths=3, zorder=5)
    ax.annotate("mustr (SMS\n+ Voice)", (0.93, 0.92),
                xytext=(0.83, 0.93), fontsize=11, color=ACCENT_SAGE,
                weight="bold", va="bottom", ha="center")

    # Arrow from today to tomorrow
    ax.annotate(
        "",
        xy=(0.91, 0.90), xytext=(0.74, 0.72),
        arrowprops=dict(arrowstyle="->", color=ACCENT_BLUE, lw=2,
                        connectionstyle="arc3,rad=0.18"),
    )

    # Axes
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel(
        "Operational autonomy   →   (does the system act on its own?)",
        fontsize=11, color=INK, labelpad=10,
    )
    ax.set_ylabel(
        "Volunteer-channel coverage   →   (SMS + Voice + Web)",
        fontsize=11, color=INK, labelpad=10,
    )

    # Cross-hair lines
    ax.axvline(0.5, color="white", lw=2, zorder=1)
    ax.axhline(0.5, color="white", lw=2, zorder=1)

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#cccccc")

    ax.set_title(
        "Competitive landscape — volunteer engagement tooling",
        fontsize=13, color=INK, weight="bold", pad=15,
    )

    plt.tight_layout()
    plt.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {out}")


# ── 2. Market sizing (nested circles) ─────────────────────────────

def build_market(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))

    # Push circles to the LEFT so labels on the right have room to breathe
    cx = 0.30
    cy = 0.50
    tam = mpatches.Circle((cx, cy), 0.36, color="#E8EEF7", ec=ACCENT_BLUE,
                          lw=2, transform=ax.transAxes)
    sam = mpatches.Circle((cx, cy), 0.24, color="#E4EDE3", ec=ACCENT_SAGE,
                          lw=2, transform=ax.transAxes)
    som = mpatches.Circle((cx, cy), 0.13, color="#F5E6E0", ec=ACCENT_PEACH,
                          lw=2, transform=ax.transAxes)
    ax.add_patch(tam)
    ax.add_patch(sam)
    ax.add_patch(som)

    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # In-circle hints (concise)
    ax.text(cx, cy + 0.30, "Crowded · slow innovation",
            fontsize=9, color=MUTE, ha="center", va="center", style="italic")
    ax.text(cx, cy + 0.18, "Underserved by AI",
            fontsize=10, color=ACCENT_SAGE, ha="center", va="center", weight="bold")
    ax.text(cx, cy, "Our beachhead",
            fontsize=11, color=ACCENT_PEACH, ha="center", va="center", weight="bold")

    # Three labels on the right, stacked vertically
    label_x = 0.70
    block_y = [0.78, 0.50, 0.22]
    blocks = [
        ("TAM", "$1.2–1.5B",
         "Global volunteer-management software market.",
         ACCENT_BLUE),
        ("SAM", "$400–600M",
         "US nonprofits, faith communities, festivals,\n"
         "and event orgs running active volunteer programs.",
         ACCENT_SAGE),
        ("SOM", "$50–100M",
         "Small-to-medium orgs (1–3 staff) running 5–50\n"
         "events/month on SMS-friendly communications.",
         ACCENT_PEACH),
    ]
    for (tag, size, desc, color), y in zip(blocks, block_y):
        # Color chip
        ax.add_patch(plt.Rectangle((label_x - 0.005, y - 0.06),
                                   0.006, 0.13, color=color,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(label_x + 0.02, y + 0.04, tag, fontsize=12,
                color=color, weight="bold", ha="left", va="center")
        ax.text(label_x + 0.08, y + 0.04, size, fontsize=20,
                color=INK, weight="bold", ha="left", va="center")
        ax.text(label_x + 0.02, y - 0.04, desc, fontsize=10,
                color=MUTE, ha="left", va="center", linespacing=1.5)

    ax.text(0.5, 0.04,
            "Sources: industry estimates from IBISWorld, NTEN, and Bloomberg Philanthropies; "
            "figures are directional.",
            fontsize=8, color=LIGHT, ha="center", style="italic")

    plt.tight_layout()
    plt.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {out}")


# ── 3. Roadmap timeline ───────────────────────────────────────────

def build_roadmap(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 5.5))

    quarters = ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "H2 2027"]
    x_positions = [0.1, 0.3, 0.5, 0.7, 0.9]

    # Spine
    ax.plot([0.05, 0.95], [0.45, 0.45], color=ACCENT_BLUE, lw=3, zorder=1)

    # Milestones — keep subtitles short and stacked vertically so they
    # never collide with the neighbouring column.
    milestones = [
        ("Q3 2026", 0.1, "GA · SMS Agent",
         "Engagement + Recruitment\nRecognition · Observability", ACCENT_BLUE),
        ("Q4 2026", 0.3, "Donations\n+ Marketing Agent",
         "Stripe Connect\nPublic donation page", ACCENT_SAGE),
        ("Q1 2027", 0.5, "Voice (Beta)",
         "Outbound check-in calls\nInbound IVR-style", ACCENT_PEACH),
        ("Q2 2027", 0.7, "Voice GA + MCP",
         "Voice billing\nExternal AI agent surface", ACCENT_LAVENDER),
        ("H2 2027", 0.9, "Enterprise &\nIntegrations",
         "SSO · Salesforce / HubSpot\n10DLC sub-accounts", ACCENT_WARM),
    ]
    for label, x, title, sub, color in milestones:
        # Dot
        ax.scatter(x, 0.45, s=400, c=color, edgecolors="white",
                   linewidths=3, zorder=4)

        # Quarter label below the dot
        ax.text(x, 0.35, label, fontsize=10, color=INK,
                weight="bold", ha="center", va="top")

        # Milestone title above the dot
        ax.text(x, 0.85, title, fontsize=11, color=INK,
                weight="bold", ha="center", va="center")
        # Subtitle below the title
        ax.text(x, 0.65, sub, fontsize=8.5, color=MUTE,
                ha="center", va="center", style="italic", linespacing=1.4)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.set_title(
        "Product roadmap — what ships, when",
        fontsize=13, color=INK, weight="bold", pad=10,
    )
    ax.text(0.5, 0.05,
            "Each milestone is a contained extension of the architecture, not a rewrite.",
            fontsize=9, color=LIGHT, ha="center", style="italic")

    plt.tight_layout()
    plt.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {out}")


def main() -> None:
    here = Path(__file__).parent
    build_competition(here / "pitch_competition_quadrant.png")
    build_market(here / "pitch_market_sizing.png")
    build_roadmap(here / "pitch_roadmap_timeline.png")


if __name__ == "__main__":
    main()
