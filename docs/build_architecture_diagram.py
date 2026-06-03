"""Render the system architecture diagram as a PNG for embedding in the
executive brief.

Run: python docs/build_architecture_diagram.py
Output: docs/architecture_diagram.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D


# Color palette — muted, executive-friendly
COLORS = {
    "channel": "#E8EEF7",        # light blue (external channels)
    "channel_edge": "#5B7AB8",
    "app": "#F1ECE4",            # warm parchment (application core)
    "app_edge": "#9C8F76",
    "agent": "#E4EDE3",          # sage (agents)
    "agent_edge": "#7BA070",
    "data": "#F5E6E0",           # pale peach (data + integrations)
    "data_edge": "#C58A6B",
    "ai": "#EDE3F2",             # lavender (AI tiers)
    "ai_edge": "#9474A6",
    "text": "#222222",
    "header": "#1A1A1A",
    "arrow": "#666666",
}


def box(ax, x, y, w, h, label, *, fill, edge, fontsize=9, weight="normal", subtitle=None):
    """Rounded box with a centered label and optional subtitle line."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(patch)
    if subtitle:
        ax.text(
            x + w / 2, y + h / 2 + 0.10, label,
            ha="center", va="center", fontsize=fontsize, weight=weight,
            color=COLORS["text"],
        )
        ax.text(
            x + w / 2, y + h / 2 - 0.16, subtitle,
            ha="center", va="center", fontsize=fontsize - 1.5, style="italic",
            color="#555555",
        )
    else:
        ax.text(
            x + w / 2, y + h / 2, label,
            ha="center", va="center", fontsize=fontsize, weight=weight,
            color=COLORS["text"],
        )


def label_band(ax, x, y, w, h, text, color):
    """A horizontal label strip used for the row dividers ('Channels',
    'Application Core', etc.)."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.04",
        linewidth=0,
        facecolor=color,
        alpha=0.55,
    ))
    ax.text(
        x + 0.10, y + h / 2, text,
        ha="left", va="center",
        fontsize=10, weight="bold", color="#333333",
    )


def arrow(ax, x1, y1, x2, y2, *, style="->", dashed=False):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        mutation_scale=12,
        linewidth=1.2,
        linestyle=("dashed" if dashed else "solid"),
        color=COLORS["arrow"],
    )
    ax.add_patch(a)


def main() -> None:
    fig, ax = plt.subplots(figsize=(13, 9.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9.5)
    ax.axis("off")

    # ── Title ────────────────────────────────────────────────────
    ax.text(
        6.5, 9.15,
        "Volunteer Engagement Platform — System Architecture",
        ha="center", va="center",
        fontsize=14, weight="bold",
        color=COLORS["header"],
    )
    ax.text(
        6.5, 8.85,
        "Multi-tenant SaaS · SMS-first volunteer operations · AI-assisted",
        ha="center", va="center",
        fontsize=10, style="italic", color="#555555",
    )

    # ── Row 1: External Channels ──────────────────────────────────
    y = 7.7
    label_band(ax, 0.2, y + 0.45, 12.6, 0.35, "EXTERNAL CHANNELS", COLORS["channel"])

    # Volunteer SMS, Admin Web, Admin SMS, Super-admin Web
    box(ax, 0.4,  y - 0.5, 2.6, 0.85,
        "Volunteers (SMS)", subtitle="Twilio inbound",
        fill=COLORS["channel"], edge=COLORS["channel_edge"], fontsize=10)
    box(ax, 3.3,  y - 0.5, 2.6, 0.85,
        "Admins (Web)", subtitle="Per-tenant panel",
        fill=COLORS["channel"], edge=COLORS["channel_edge"], fontsize=10)
    box(ax, 6.2,  y - 0.5, 2.6, 0.85,
        "Admins (SMS)", subtitle="STATUS, APPROVE, RESERVE",
        fill=COLORS["channel"], edge=COLORS["channel_edge"], fontsize=10)
    box(ax, 9.1,  y - 0.5, 3.7, 0.85,
        "Super-Admin (Web)", subtitle="Tenant provisioning, billing, fleet ops",
        fill=COLORS["channel"], edge=COLORS["channel_edge"], fontsize=10)

    # ── Row 2: Application Core ──────────────────────────────────
    y = 6.1
    label_band(ax, 0.2, y + 0.55, 12.6, 0.35, "APPLICATION CORE (FastAPI)", COLORS["app"])

    # Webhook + Pipeline (left)
    box(ax, 0.4, y - 0.3, 3.4, 0.85,
        "Inbound Webhook",
        subtitle="Tenant resolution · Idempotency · 200-OK + BG task",
        fill=COLORS["app"], edge=COLORS["app_edge"], fontsize=10)

    # Web API
    box(ax, 4.1, y - 0.3, 3.4, 0.85,
        "Web API (REST)",
        subtitle="Role gates · Tenant scoping · Rate limiting",
        fill=COLORS["app"], edge=COLORS["app_edge"], fontsize=10)

    # Scheduler
    box(ax, 7.8, y - 0.3, 2.4, 0.85,
        "Scheduler (APScheduler)",
        subtitle="Reminders, pings, auto-close",
        fill=COLORS["app"], edge=COLORS["app_edge"], fontsize=10)

    # MCP / external agents (forward looking)
    box(ax, 10.5, y - 0.3, 2.3, 0.85,
        "Audit + Observability",
        subtitle="agent_call_log · metrics",
        fill=COLORS["app"], edge=COLORS["app_edge"], fontsize=10)

    # ── Row 3: Orchestrator + Agents ──────────────────────────────
    y = 4.6
    label_band(ax, 0.2, y + 0.55, 12.6, 0.35, "AGENT LAYER (Path A architecture)", COLORS["agent"])

    # Orchestrator (centered)
    box(ax, 4.7, y - 0.25, 3.6, 0.85,
        "Orchestrator",
        subtitle="Dispatcher · Crisis / Cooldown / Quiet Hours / Takeover",
        fill=COLORS["agent"], edge=COLORS["agent_edge"], fontsize=10, weight="bold")

    # Three domain agents below
    by = y - 1.55
    box(ax, 0.4, by, 3.0, 0.85,
        "Engagement Agent",
        subtitle="Check-in · DONE · SWITCH · ALSO · Pings",
        fill=COLORS["agent"], edge=COLORS["agent_edge"], fontsize=10)
    box(ax, 3.6, by, 3.0, 0.85,
        "Recruiter + Scheduler",
        subtitle="Plans waves · Books · RESERVE",
        fill=COLORS["agent"], edge=COLORS["agent_edge"], fontsize=10)
    box(ax, 6.8, by, 3.0, 0.85,
        "Marketing Agent",
        subtitle="Donations · Outreach · Reports",
        fill=COLORS["agent"], edge=COLORS["agent_edge"], fontsize=10)
    box(ax, 10.0, by, 2.8, 0.85,
        "Review + Recognition",
        subtitle="Grading · Auto-awards · Quality score",
        fill=COLORS["agent"], edge=COLORS["agent_edge"], fontsize=10)

    # ── Row 4: Hybrid Intent Stack (cross-cutting) ───────────────
    y = 2.2
    label_band(ax, 0.2, y + 0.55, 12.6, 0.35, "HYBRID INTENT STACK (per message)", COLORS["ai"])

    box(ax, 0.4, y - 0.25, 4.0, 0.85,
        "Tier 1 · Pattern Rules",
        subtitle="~5ms · $0 · ~80–90% of messages",
        fill=COLORS["ai"], edge=COLORS["ai_edge"], fontsize=10, weight="bold")
    box(ax, 4.6, y - 0.25, 4.0, 0.85,
        "Tier 2 · Haiku Classifier",
        subtitle="~300ms · ~$0.0001 · long-tail phrasings",
        fill=COLORS["ai"], edge=COLORS["ai_edge"], fontsize=10)
    box(ax, 8.8, y - 0.25, 4.0, 0.85,
        "Tier 3 · Full LLM + Tools",
        subtitle="~1–2s · ~$0.005–0.015 · open questions",
        fill=COLORS["ai"], edge=COLORS["ai_edge"], fontsize=10)

    # Inter-tier arrows
    arrow(ax, 4.4, y + 0.15, 4.6, y + 0.15)
    arrow(ax, 8.6, y + 0.15, 8.8, y + 0.15)

    # ── Row 5: Data & Integrations ───────────────────────────────
    y = 0.55
    label_band(ax, 0.2, y + 0.55, 12.6, 0.35, "DATA & EXTERNAL INTEGRATIONS", COLORS["data"])

    box(ax, 0.4, y - 0.25, 3.0, 0.85,
        "PostgreSQL (Supabase)",
        subtitle="Multi-tenant · tenant_id on every row",
        fill=COLORS["data"], edge=COLORS["data_edge"], fontsize=10)
    box(ax, 3.6, y - 0.25, 2.3, 0.85,
        "Twilio",
        subtitle="SMS + sub-accounts",
        fill=COLORS["data"], edge=COLORS["data_edge"], fontsize=10)
    box(ax, 6.1, y - 0.25, 2.3, 0.85,
        "Anthropic Claude",
        subtitle="Haiku + Sonnet",
        fill=COLORS["data"], edge=COLORS["data_edge"], fontsize=10)
    box(ax, 8.6, y - 0.25, 2.0, 0.85,
        "Google Calendar",
        subtitle="OAuth per tenant",
        fill=COLORS["data"], edge=COLORS["data_edge"], fontsize=10)
    box(ax, 10.8, y - 0.25, 2.0, 0.85,
        "Resend (Email)",
        subtitle="Transactional",
        fill=COLORS["data"], edge=COLORS["data_edge"], fontsize=10)

    # ── Vertical flow arrows (channels → app → agents → intent → data) ─
    # Volunteer SMS down through webhook → engagement
    arrow(ax, 1.7, 7.2, 1.7, 6.65)            # channel → webhook
    arrow(ax, 2.1, 5.8, 4.7, 5.0)             # webhook → orchestrator
    arrow(ax, 6.5, 4.35, 3.05, 3.45)          # orch → engagement
    arrow(ax, 6.5, 4.35, 5.1, 3.45)           # orch → recruiter+scheduler
    arrow(ax, 6.5, 4.35, 8.3, 3.45)           # orch → marketing
    arrow(ax, 6.5, 4.35, 11.4, 3.45)          # orch → review+recognition

    # Admin Web → Web API
    arrow(ax, 4.6, 7.2, 4.6, 6.65)
    # Admin SMS → Webhook (admins also text in)
    arrow(ax, 7.5, 7.2, 2.4, 6.65, dashed=True)
    # Super-admin → Web API
    arrow(ax, 10.95, 7.2, 7.0, 6.65)

    # Agents → Hybrid Intent Stack (cross-cutting)
    arrow(ax, 1.9, 2.6, 2.4, 2.6, style="-")
    # Each agent box dotted into the intent stack to indicate "uses"
    arrow(ax, 1.9, 3.45, 1.9, 2.7, dashed=True)
    arrow(ax, 5.1, 3.45, 5.1, 2.7, dashed=True)
    arrow(ax, 8.3, 3.45, 8.3, 2.7, dashed=True)

    # Intent tiers → Data
    arrow(ax, 2.4, 1.7, 2.4, 1.25)
    arrow(ax, 6.6, 1.7, 4.7, 1.25)
    arrow(ax, 6.6, 1.7, 7.2, 1.25)
    arrow(ax, 10.8, 1.7, 11.8, 1.25)

    # Scheduler → Twilio (outbound pings/reminders) — dashed cross-link
    arrow(ax, 9.0, 5.8, 4.7, 1.25, dashed=True)
    # Web API → DB
    arrow(ax, 5.8, 5.8, 1.9, 1.25, dashed=True)
    # Webhook → DB (audit + pending_intent + checkin writes)
    arrow(ax, 2.1, 5.8, 1.9, 1.25, dashed=True)

    # ── Legend ───────────────────────────────────────────────────
    legend_handles = [
        Line2D([0], [0], color=COLORS["arrow"], linewidth=1.4, linestyle="-",
               label="Primary request flow"),
        Line2D([0], [0], color=COLORS["arrow"], linewidth=1.4, linestyle="--",
               label="Background / cross-cutting"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8,
              frameon=True, framealpha=0.9, edgecolor="#cccccc",
              bbox_to_anchor=(0.99, 0.005))

    out = Path(__file__).parent / "architecture_diagram.png"
    plt.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
