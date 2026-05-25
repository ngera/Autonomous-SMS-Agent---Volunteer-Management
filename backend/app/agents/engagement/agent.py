"""Engagement Agent — skeleton.

Today: never selected by the Orchestrator router (no conversation has
owning_agent='engagement' yet). When the top-3 feature work lands:
  - The day-of HERE intent router (intents.py) will be invoked from
    within the orchestrator's pre-LLM short-circuit path.
  - When a booking gets within 48h of its slot, executor.py sets
    conversation.owning_agent='engagement' so engagement-flavored
    replies (running late, swap, cancel) route here first.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AGENT_ENGAGEMENT, AgentResponse, BaseAgent


class EngagementAgent:
    """Skeleton. handle_inbound is a no-op until top-3 work fills it."""

    name: str = AGENT_ENGAGEMENT

    async def handle_inbound(
        self,
        db: AsyncSession,
        tenant,
        from_phone: str,
        message: str,
        *,
        conversation,
        turn_id: uuid.UUID,
    ) -> AgentResponse:
        # When the orchestrator routes here today (only if a previous
        # caller explicitly flipped conversation.owning_agent), we
        # transfer back to the recruiter_scheduler — the safe default.
        # Top-3 work replaces this with the real engagement intents.
        from app.agents.base import AGENT_RECRUITER_SCHEDULER
        return AgentResponse(
            reply_text=None,
            transfer_to=AGENT_RECRUITER_SCHEDULER,
            tool_calls=[],
            state_snapshot={"engagement_skeleton": True},
            metadata={"turn_id": str(turn_id)},
        )

    async def start_workflow(
        self,
        db: AsyncSession,
        tenant,
        workflow_id: uuid.UUID,
        config: dict,
    ) -> str | None:
        # When implemented: scheduled day-of reminders, thank-yous,
        # no-show follow-ups, lapsed re-engagement. Today: None.
        return None

    async def status(self, db: AsyncSession, tenant, workflow_id: uuid.UUID) -> dict:
        return {"workflow_id": str(workflow_id), "owner": self.name, "exists": False}

    async def health_check(self) -> dict:
        return {"ok": True, "message": "engagement skeleton (no impl yet)"}


_instance: BaseAgent = EngagementAgent()
