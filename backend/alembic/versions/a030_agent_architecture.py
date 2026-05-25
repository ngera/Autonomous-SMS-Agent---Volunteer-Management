"""Path A foundation — agent_call_log table, per-tenant agent_models +
cross-cutting policy columns, conversation owning_agent + takeover,
contact last_outbound_at + timezone for cross-agent cooldown + quiet hours.

All additive; no behavior change. The Orchestrator (new) reads these
columns; each BaseAgent records routing decisions + tool calls into
agent_call_log so we have graph-shaped observability from day one.

See memory/path_a_agent_architecture_plan.md.

Revision ID: a030_agent_architecture
Revises: a029_announcement_delete_cascade
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a030_agent_architecture"
down_revision: Union[str, None] = "a029_announcement_delete_cascade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Per-tenant agent + cross-cutting policy config ──
    op.execute(
        """
        ALTER TABLE tenants
          ADD COLUMN IF NOT EXISTS agent_models JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS cross_agent_cooldown_hours INTEGER NOT NULL DEFAULT 24,
          ADD COLUMN IF NOT EXISTS per_volunteer_weekly_cap INTEGER NOT NULL DEFAULT 5,
          ADD COLUMN IF NOT EXISTS quiet_hours_start TIME DEFAULT '21:00',
          ADD COLUMN IF NOT EXISTS quiet_hours_end TIME DEFAULT '09:00';
        """
    )

    # ── Conversation ownership + take-over ──
    # owning_agent is NULL for legacy rows; the Orchestrator router falls
    # back to recruiter_scheduler when NULL. takeover_mode pauses agent
    # outbound; takeover_admin_id records who took over.
    op.execute(
        """
        ALTER TABLE conversations
          ADD COLUMN IF NOT EXISTS owning_agent TEXT,
          ADD COLUMN IF NOT EXISTS takeover_mode BOOLEAN NOT NULL DEFAULT false,
          ADD COLUMN IF NOT EXISTS takeover_admin_id UUID
            REFERENCES admin_users(id) ON DELETE SET NULL;
        """
    )

    # ── Contact-level cross-agent state ──
    # last_outbound_at gets updated by every agent on every send so the
    # Orchestrator can enforce a tenant-wide N-hour cooldown across
    # agents. timezone defaults to NULL; quiet-hours check skips when
    # NULL (per the plan's open question — pre-populating from tenant
    # timezone is left for a follow-up).
    op.execute(
        """
        ALTER TABLE contacts
          ADD COLUMN IF NOT EXISTS last_outbound_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS timezone TEXT;
        """
    )

    # ── agent_call_log: graph-shaped audit ──
    # Every Orchestrator routing decision + every BaseAgent invocation +
    # every tool call writes a row. Rows from one inbound message share
    # a turn_id so the trace UI can group them.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_call_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
            turn_id UUID NOT NULL,

            source_agent TEXT NOT NULL,
            destination_agent TEXT,
            event_type TEXT NOT NULL,

            decision_reason TEXT,
            state_snapshot JSONB,

            tool_name TEXT,
            tool_input JSONB,
            tool_output_summary TEXT,
            model_used TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER,
            status TEXT NOT NULL DEFAULT 'ok',
            error_message TEXT,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_call_log_conversation
          ON agent_call_log (conversation_id, created_at DESC)
          WHERE conversation_id IS NOT NULL;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_call_log_turn ON agent_call_log (turn_id);"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_call_log_tenant_time
          ON agent_call_log (tenant_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_call_log_tenant_time;")
    op.execute("DROP INDEX IF EXISTS ix_agent_call_log_turn;")
    op.execute("DROP INDEX IF EXISTS ix_agent_call_log_conversation;")
    op.execute("DROP TABLE IF EXISTS agent_call_log;")
    op.execute(
        """
        ALTER TABLE contacts
          DROP COLUMN IF EXISTS timezone,
          DROP COLUMN IF EXISTS last_outbound_at;
        """
    )
    op.execute(
        """
        ALTER TABLE conversations
          DROP COLUMN IF EXISTS takeover_admin_id,
          DROP COLUMN IF EXISTS takeover_mode,
          DROP COLUMN IF EXISTS owning_agent;
        """
    )
    op.execute(
        """
        ALTER TABLE tenants
          DROP COLUMN IF EXISTS quiet_hours_end,
          DROP COLUMN IF EXISTS quiet_hours_start,
          DROP COLUMN IF EXISTS per_volunteer_weekly_cap,
          DROP COLUMN IF EXISTS cross_agent_cooldown_hours,
          DROP COLUMN IF EXISTS agent_models;
        """
    )
