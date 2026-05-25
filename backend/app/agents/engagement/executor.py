"""Engagement executor — cron-driven dispatch.

Skeleton. Top-3 feature work fills this with:
  - send_morning_reminder(booking) — T-2h reminder
  - send_no_show_followup(booking) — "running late?" after T+15min
  - trigger_backfill(slot) — when a booking cancels within 48h
  - send_thank_you(booking) — 1h after slot end
  - send_lapsed_reengagement(contact) — for contacts whose last
    booking was > N days ago
  - send_milestone(contact) — birthday, Nth event, etc.

Pattern mirrors app/agents/recruiter/executor.py: deterministic
dispatch + occasional LLM seam (via reporter.py for narrative).
"""
