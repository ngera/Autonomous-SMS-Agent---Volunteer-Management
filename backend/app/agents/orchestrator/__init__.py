"""Orchestrator — supervisor layer that routes inbound SMS to the right
agent and enforces cross-cutting policy (cooldowns, quiet hours, crisis
detection, take-over).

Has no LLM in its own request path; uses Haiku only in classifier seams
(crisis detection). See memory/path_a_agent_architecture_plan.md.
"""

from app.agents.orchestrator.router import handle_inbound

__all__ = ["handle_inbound"]
