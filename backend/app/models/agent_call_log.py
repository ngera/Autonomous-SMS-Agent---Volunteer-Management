"""Graph-style audit log of every agent invocation, routing decision,
and tool call. See migration a030 + memory/path_a_agent_architecture_plan.md.
"""
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentCallLog(Base):
    __tablename__ = "agent_call_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    # Groups all rows from one inbound message turn so the Trace UI can
    # render them together. Generated at the Orchestrator entrypoint.
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    source_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # See app.agents.base.EVENT_* constants for the canonical vocabulary.
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Capped, redacted summary so log rows don't carry PII or huge payloads.
    tool_output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ok"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
