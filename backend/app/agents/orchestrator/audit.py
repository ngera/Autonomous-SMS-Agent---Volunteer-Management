"""Writer for the agent_call_log graph-shaped audit trail.

Every Orchestrator routing decision, every BaseAgent.handle_inbound
entry/exit, every tool call, every LLM call writes a row here. The
Conversation Trace UI groups by ``turn_id``.

All write helpers are no-throw — audit failure must never break the
calling request path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.agent_call_log import AgentCallLog

logger = get_logger("orchestrator.audit")

_OUTPUT_SUMMARY_CAP = 500


def _summarize(value: object | None) -> str | None:
    """Stringify + truncate for tool_output_summary."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if len(text) <= _OUTPUT_SUMMARY_CAP:
        return text
    return text[:_OUTPUT_SUMMARY_CAP] + "…[truncated]"


async def record(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    turn_id: uuid.UUID,
    source_agent: str,
    event_type: str,
    conversation_id: uuid.UUID | None = None,
    destination_agent: str | None = None,
    decision_reason: str | None = None,
    state_snapshot: dict | None = None,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    tool_output_summary: str | None = None,
    model_used: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    status: str = "ok",
    error_message: str | None = None,
) -> None:
    """Append one row to agent_call_log.

    Swallows its own exceptions — audit writes must never break the
    calling code path (mirrors the issue_logging pattern from the
    issue-reporting plan).
    """
    try:
        row = AgentCallLog(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            source_agent=source_agent,
            destination_agent=destination_agent,
            event_type=event_type,
            decision_reason=decision_reason,
            state_snapshot=state_snapshot,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output_summary=_summarize(tool_output_summary),
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        db.add(row)
        await db.flush()
    except Exception:  # noqa: BLE001
        logger.exception(
            "agent_call_log write failed (tenant=%s turn=%s event=%s)",
            tenant_id, turn_id, event_type,
        )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
