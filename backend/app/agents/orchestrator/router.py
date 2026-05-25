"""Inbound SMS router — the Orchestrator's main entrypoint.

Flow:
  1. Resolve conversation + contact (or admin)
  2. Crisis-language check on the inbound message → if hit, pause + escalate
  3. Take-over check → if admin has taken over, silently log + return
  4. Determine owning agent (conversations.owning_agent; default recruiter_scheduler)
  5. Audit: route event
  6. Dispatch to BaseAgent.handle_inbound
  7. Apply transfer_to if returned

Phase 1 keeps the existing pipeline.process_inbound_message as the
implementation behind RecruiterSchedulerAgent. The Orchestrator's job
in Phase 1 is mostly to *exist* and *record* — the policy enforcement
points (cooldown, quiet hours, crisis) are wired but mostly observe.
Phase 2 (compliance bundle) flips them to enforce.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AGENT_ORCHESTRATOR,
    AGENT_RECRUITER_SCHEDULER,
    EVENT_ESCALATE,
    EVENT_PAUSE,
    EVENT_ROUTE,
)
from app.agents.orchestrator import audit, crisis, registry, takeover
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationStatus
from app.models.tenant import Tenant

logger = get_logger("orchestrator.router")


async def handle_inbound(
    db: AsyncSession,
    from_phone: str,
    message_body: str,
    tenant_id: uuid.UUID,
) -> None:
    """Top-level entry for an inbound SMS.

    Replaces direct calls to pipeline.process_inbound_message. The
    actual conversation work still happens in the same code (via the
    RecruiterSchedulerAgent's handle_inbound), but it's now wrapped
    in routing + audit + policy hooks.

    Errors here are non-fatal at the framework level — the caller
    (webhook background task) catches and rolls back. We log + record
    audit but don't re-raise on policy violations.
    """
    turn_id = uuid.uuid4()

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()

    # Resolve contact (None for admin senders — those are detected
    # inside RecruiterSchedulerAgent today, same as before)
    contact = (
        await db.execute(
            select(Contact).where(
                Contact.phone == from_phone,
                Contact.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    # Resolve the most recent active conversation (customer-side) so
    # we can check take-over state. Admin conversations are routed
    # inside the agent itself.
    conv_row = (
        await db.execute(
            select(Conversation)
            .where(
                Conversation.contact_phone == from_phone,
                Conversation.tenant_id == tenant_id,
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.sender_type == "customer",
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # ── Crisis pre-filter ──
    # Rule-based today; LLM classifier in Phase 2 compliance bundle.
    crisis_decision = await crisis.check(message_body)
    if crisis_decision.is_crisis:
        await audit.record(
            db,
            tenant_id=tenant_id,
            turn_id=turn_id,
            source_agent=AGENT_ORCHESTRATOR,
            event_type=EVENT_ESCALATE,
            conversation_id=conv_row.id if conv_row else None,
            decision_reason=crisis_decision.reason,
            state_snapshot={"severity": crisis_decision.severity, "from": from_phone},
            status="ok",
        )
        # Phase 2: pause conversation + create issue_report + notify admin.
        # Phase 1: log only — let the regular pipeline still respond so
        # we don't accidentally ghost a volunteer mid-crisis until the
        # downstream escalation flow is built. (The audit row is the
        # forensic record we need for now.)
        logger.warning(
            "Crisis language detected from %s tenant=%s reason=%s",
            from_phone, tenant_id, crisis_decision.reason,
        )

    # ── Take-over check ──
    takeover_state = takeover.state_of(conv_row)
    if takeover_state.in_takeover:
        await audit.record(
            db,
            tenant_id=tenant_id,
            turn_id=turn_id,
            source_agent=AGENT_ORCHESTRATOR,
            event_type=EVENT_PAUSE,
            conversation_id=conv_row.id if conv_row else None,
            decision_reason="conversation in admin take-over mode",
            state_snapshot={"takeover_admin_id": str(takeover_state.admin_id)},
        )
        return

    # ── Determine owning agent ──
    owning = (conv_row.owning_agent if conv_row and getattr(conv_row, "owning_agent", None)
              else AGENT_RECRUITER_SCHEDULER)
    agent = registry.get(owning)
    if agent is None:
        logger.error(
            "No agent registered for owning_agent=%s; falling back to recruiter_scheduler",
            owning,
        )
        owning = AGENT_RECRUITER_SCHEDULER
        agent = registry.get(owning)
        if agent is None:
            await audit.record(
                db,
                tenant_id=tenant_id,
                turn_id=turn_id,
                source_agent=AGENT_ORCHESTRATOR,
                event_type=EVENT_ROUTE,
                conversation_id=conv_row.id if conv_row else None,
                decision_reason="no agent available",
                status="error",
                error_message="registry returned None for recruiter_scheduler",
            )
            return

    # ── Audit the route ──
    await audit.record(
        db,
        tenant_id=tenant_id,
        turn_id=turn_id,
        source_agent=AGENT_ORCHESTRATOR,
        destination_agent=owning,
        event_type=EVENT_ROUTE,
        conversation_id=conv_row.id if conv_row else None,
        decision_reason=(
            f"conversation.owning_agent={conv_row.owning_agent if conv_row else None}"
            if conv_row else "no active conversation; defaulting"
        ),
        state_snapshot={"from": from_phone, "tenant": str(tenant_id)},
    )

    # ── Dispatch ──
    # The agent's handle_inbound is responsible for everything from here:
    # building the response, sending SMS, persisting conversation history.
    # We pass turn_id so the agent's tool/LLM calls land in the same trace.
    try:
        response = await agent.handle_inbound(
            db=db,
            tenant=tenant,
            from_phone=from_phone,
            message=message_body,
            conversation=conv_row,
            turn_id=turn_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Agent %s failed handle_inbound for %s tenant=%s",
            owning, from_phone, tenant_id,
        )
        await audit.record(
            db,
            tenant_id=tenant_id,
            turn_id=turn_id,
            source_agent=owning,
            event_type="error",
            conversation_id=conv_row.id if conv_row else None,
            status="error",
            error_message=str(exc)[:500],
        )
        raise

    # ── Handle transfer_to (when an agent wants to hand the thread off) ──
    if response.transfer_to and conv_row is not None:
        conv_row.owning_agent = response.transfer_to
        await db.flush()
        await audit.record(
            db,
            tenant_id=tenant_id,
            turn_id=turn_id,
            source_agent=owning,
            destination_agent=response.transfer_to,
            event_type=EVENT_ROUTE,
            conversation_id=conv_row.id,
            decision_reason=f"transfer_to from {owning}",
        )

    # Note: Sending the reply SMS and persisting message_history are
    # the AGENT's responsibility today — keeps Phase 1 a no-behavior-
    # change refactor. A future refactor could pull those into the
    # router so agents only return AgentResponse, but that requires
    # touching every agent simultaneously.
    _ = contact  # used by Phase-2 cooldown.record_outbound when wired in
