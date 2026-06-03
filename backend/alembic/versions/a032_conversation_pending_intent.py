"""Add conversations.pending_intent + pending_intent_expires_at for
multi-stage SMS state. Powers Row 1 Edge A (back-to-back disambiguation),
Row 1 Edge C (HERE-AGAIN re-entry), Row 2 walk-up event/service picker,
and RESERVE 2-stage parsing.

Verified missing from current schema before this migration (review pass
issue #14). JSONB shape is a discriminated union by `intent_type`; see
event_lifecycle_plan.md canonical schema section for full doc.

Partial index `WHERE pending_intent IS NOT NULL` is for cleanup
observability, not hot reads — hot reads use the conversation_id PK.

Revision ID: a032_conversation_pending_intent
Revises: a031_contact_roster_default
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a032_conversation_pending_intent"
down_revision: Union[str, None] = "a031_contact_roster_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE conversations
          ADD COLUMN IF NOT EXISTS pending_intent JSONB,
          ADD COLUMN IF NOT EXISTS pending_intent_expires_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_conv_pending_intent_active
          ON conversations (tenant_id, pending_intent_expires_at)
          WHERE pending_intent IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conv_pending_intent_active;")
    op.execute(
        """
        ALTER TABLE conversations
          DROP COLUMN IF EXISTS pending_intent_expires_at,
          DROP COLUMN IF EXISTS pending_intent;
        """
    )
