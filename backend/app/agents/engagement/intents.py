"""Engagement intent routers — server-side short-circuit before LLM.

Skeleton. Will host (same pattern as design_decisions.md #7):
  - maybe_handle_here_check_in(contact, body) → "HERE", "arrived",
    "I'm here" → mark booking.checked_in_at + reply confirmation
  - maybe_handle_running_late(contact, body) → "running late", "stuck
    in traffic", "on my way" → mark booking metadata + reply
  - maybe_handle_pause_communications(contact, body) → "don't text
    me", "pause" → set contact.communications_paused_until
"""
