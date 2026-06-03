"""BaseAgent Protocol — the contract every agent satisfies.

Internal Python agents (recruiter_scheduler, engagement, planner_*,
marketing, future onboarding, reporting, coaching) and external agents
(REST or MCP-based; see donation_campaigns_plan.md + mcp_server_plan.md)
both implement this same shape. The Orchestrator only knows about
BaseAgent — it never reaches into agent-specific internals.

See memory/path_a_agent_architecture_plan.md.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# Event-type vocabulary for agent_call_log.event_type. Kept here so
# every agent uses the same strings.
EVENT_ROUTE = "route"            # Orchestrator picked an agent
EVENT_TOOL_CALL = "tool_call"    # Agent invoked a tool
EVENT_LLM_CALL = "llm_call"      # Agent called the LLM
EVENT_SEND_SMS = "send_sms"      # Agent sent an outbound SMS
EVENT_PAUSE = "pause"            # Orchestrator paused agent action
EVENT_ESCALATE = "escalate"      # Crisis detector escalated to human
EVENT_AGENT_HANDLE = "agent_handle"  # BaseAgent.handle_inbound entered

# ── Event lifecycle plan additions (decision #31) ──
EVENT_VOLUNTEER_CHECK_IN = "volunteer_check_in"    # decision #10, Row 1 (segments)
EVENT_VOLUNTEER_CHECK_OUT = "volunteer_check_out"  # decision #10, Row 1 (segments)
EVENT_ADMIN_OVERRIDE = "admin_override"            # decision #3 (admin edits booking/service_log)
EVENT_REVIEW_UNLOCKED = "review_unlocked"          # decision #16 (OWNER unlock of approved review)


# Canonical agent names. Use these as string literals (not enums) so
# external agents declaring their `name` don't need to import our code.
AGENT_ORCHESTRATOR = "orchestrator"
AGENT_RECRUITER_SCHEDULER = "recruiter_scheduler"
AGENT_ENGAGEMENT = "engagement"
AGENT_PLANNER_RECRUITMENT = "planner_recruitment"
AGENT_MARKETING = "marketing"


@dataclass(frozen=True)
class AgentResponse:
    """Returned from BaseAgent.handle_inbound.

    The Orchestrator decides what to do with each field:
      - reply_text → send outbound SMS to the volunteer (None = silent)
      - transfer_to → hand thread ownership to this other agent
      - tool_calls → audit log (in addition to per-tool rows already written)
      - state_snapshot → recorded in the parent agent_call_log row
      - metadata → agent-specific, opaque to Orchestrator
    """
    reply_text: str | None = None
    transfer_to: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    state_snapshot: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class BaseAgent(Protocol):
    """The interface every agent implements.

    Implementations live as Python modules in app/agents/<name>/
    exposing a class that satisfies this Protocol. The Orchestrator
    registers them at startup via app/agents/orchestrator/registry.py.

    Implementations MUST be idempotent on conversation state — the
    Orchestrator may retry a failed turn, and we never want a duplicate
    SMS as a result.
    """

    name: str  # one of the AGENT_* constants above (or an external agent's id)

    async def handle_inbound(
        self,
        db,
        tenant,
        from_phone: str,
        message: str,
        *,
        conversation,
        turn_id: uuid.UUID,
    ) -> AgentResponse:
        """Process an inbound SMS this agent owns.

        ``from_phone`` is the canonical identifier — ``conversation``
        may be None for a first-message contact (the agent may have to
        create it). ``turn_id`` groups all agent_call_log rows from one
        inbound turn so the Trace UI can render them together.
        """

    async def start_workflow(
        self,
        db,
        tenant,
        workflow_id: uuid.UUID,
        config: dict,
    ) -> str | None:
        """Kick off a long-running campaign or process.

        Returns a job id string if async, None if synchronous. For the
        recruitment planner this is "run plan"; for engagement it's
        "fire scheduled wave"; for marketing it's "start outreach".

        Agents that don't have a workflow concept return None.
        """

    async def status(self, db, tenant, workflow_id: uuid.UUID) -> dict:
        """Snapshot of a workflow's state for the admin UI."""

    async def health_check(self) -> dict:
        """Liveness check: {ok: bool, message: str}."""
