"""Engagement Agent — everything that happens AFTER signup.

Today (Path A): skeleton with no real implementation. The agent's
handle_inbound returns AgentResponse() (no-op) and start_workflow
returns None. Existing reminder code in app/scheduler/jobs.py stays
where it is.

Top-3 feature work fills this module with:
  - executor.py: cron-driven dispatch for thank-yous, no-show
    follow-up, lapsed re-engagement, milestone recognition, backfill
    on last-minute cancel.
  - reporter.py: post-shift personalized thank-you LLM seam.
  - intents.py: server-side routers for HERE / "running late" /
    "STOP this reminder" on a per-thread basis.
  - planner.py: only added if engagement gains a planning surface
    (e.g., re-engagement campaign planning).
"""

from app.agents.engagement.agent import EngagementAgent

__all__ = ["EngagementAgent"]
