"""Phase 1 step 5a — volunteer_candidate table for Row 4/5
unknown-phone capture.

The candidate-vs-Contact split keeps the contacts table free of
anonymous UNCONTACTED stubs. Unknown phones land here via the webhook
pipeline branch (Row 4 / Row 5); admin acts on them via /candidates UI
to either Invite (promotes to a real Contact) or Dismiss.

Decisions:
  - #29(c): predicate-narrow DELETE in the auto-prune job is race-safe
    against concurrent Invite/Dismiss (uses invited_at IS NULL AND
    dismissed_at IS NULL)
  - #32: 1-year retention cap on terminal states (dismissed, invited)

last_notified_at powers the 24h notification rate limit so a stranger
texting repeatedly doesn't spam admins.

Revision ID: a036_volunteer_candidate
Revises: a035_bookings_checkin_columns
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a036_volunteer_candidate"
down_revision: Union[str, None] = "a035_bookings_checkin_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteer_candidate (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone VARCHAR(20) NOT NULL,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_notified_at TIMESTAMPTZ,
            occurrence_count INT NOT NULL DEFAULT 1,
            last_signal_slot_id UUID REFERENCES specific_date_slots(id) ON DELETE SET NULL,
            last_message_body TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            invited_at TIMESTAMPTZ,
            invited_by_admin_id UUID REFERENCES admin_users(id),
            dismissed_at TIMESTAMPTZ,
            dismissed_by_admin_id UUID REFERENCES admin_users(id),
            promoted_contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
            notes TEXT,
            UNIQUE (tenant_id, phone),
            CONSTRAINT ck_candidate_status CHECK (
              status IN ('new', 'invited', 'dismissed')
            )
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_candidate_status
          ON volunteer_candidate (tenant_id, status, last_seen_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS volunteer_candidate CASCADE;")
