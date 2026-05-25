"""BaseAgent implementation for Recruiter+Scheduler.

Path A: thin adapter that delegates to the existing pipeline.
process_inbound_message. The pipeline still owns:
  - Admin SMS detection + handling
  - Opt-out keyword check
  - Consent flow
  - Screener (Stage 1 rule + Stage 2 LLM)
  - Strike / suspension
  - Customer LLM tool-use loop
  - Conversation history persistence
  - Outbound SMS send
  - Memory extraction on booking close

The Orchestrator's policy hooks (cooldown / quiet_hours / crisis) wrap
this externally — they don't reach into the pipeline. When Phase 2
pulls policy enforcement to the Orchestrator level, this agent's
handle_inbound stays the same; only what wraps it changes.

Future work in this module (top-3 features land here):
  - intents.py: server-side routers for HERE / "running late" / profile-
    update / pause / etc.
  - tools.py: tool registry extensions (update_my_profile, log_hours, ...)
  - prompts.py: per-tenant prompt customization beyond what conversation.py owns
  - planner.py: NOT NEEDED — Recruiter is reactive, not planned (Planner
    Agent owns campaign planning)
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AGENT_RECRUITER_SCHEDULER,
    AgentResponse,
    BaseAgent,
)
from app.core.logging import get_logger

logger = get_logger("agents.recruiter_scheduler")


class RecruiterSchedulerAgent:
    """Adapter that satisfies the BaseAgent Protocol while delegating
    actual work to the existing pipeline.
    """

    name: str = AGENT_RECRUITER_SCHEDULER

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
        # Phase 1 delegation: existing pipeline.process_inbound_message
        # contains ALL the customer-side logic (admin detection,
        # consent, screener, strikes, LLM tool loop, SMS send, history
        # persistence). We just hand off and let it run.
        #
        # `turn_id` is captured here for future use — once the
        # pipeline starts writing tool/llm_call audit rows, it'll
        # consume turn_id from a contextvar that this method sets.
        from app.modules import pipeline

        await pipeline.process_inbound_message(
            db=db,
            from_phone=from_phone,
            message_body=message,
            tenant_id=tenant.id,
        )

        # The pipeline already sent the SMS + persisted history. We
        # return an empty AgentResponse — Orchestrator router doesn't
        # do any additional send work today.
        return AgentResponse(
            reply_text=None,
            transfer_to=None,
            tool_calls=[],
            state_snapshot={"delegated_to": "pipeline.process_inbound_message"},
            metadata={"turn_id": str(turn_id)},
        )

    async def start_workflow(
        self,
        db: AsyncSession,
        tenant,
        workflow_id: uuid.UUID,
        config: dict,
    ) -> str | None:
        """Recruiter+Scheduler is reactive — no agent-owned workflows.

        Campaign workflows belong to the Planner agent (existing
        app/agents/recruiter/, to be renamed planner_recruitment).
        """
        return None

    async def status(self, db: AsyncSession, tenant, workflow_id: uuid.UUID) -> dict:
        return {"workflow_id": str(workflow_id), "owner": self.name, "exists": False}

    async def health_check(self) -> dict:
        return {"ok": True, "message": f"{self.name} delegating to pipeline"}


# Module-level singleton check at import time — confirms the class
# satisfies the BaseAgent Protocol shape. Cheap; catches drift.
_instance: BaseAgent = RecruiterSchedulerAgent()
