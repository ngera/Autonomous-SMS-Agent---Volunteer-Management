"""Phase 2 — Roster status auto-pings.

Schema additions:
  - roster_status_ping_log table (observability + pre-insert silencing).
    CHECK constraints on channel + skipped_reason per the locked plan.
  - admin_users.status_pings_opted_out BOOLEAN DEFAULT FALSE
    (powers STOP STATUS ALL — global opt-out per admin).

Decisions:
  - #9: 7 ping times per slot (T-30, T-15, T, T+15, T+30, T+45, T+60).
  - Suppression rule: when everyone is checked in, send one
    "All checked in ✓" then mark remaining T+* rows as
    skipped_reason='event_full_checked_in'.

Revision ID: a038_roster_status_ping_log
Revises: a037_notification_walkup_candidate
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a038_roster_status_ping_log"
down_revision: Union[str, None] = "a037_notification_walkup_candidate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Required for ALTER TYPE ... ADD VALUE on PG ≤11.
transactional_ddl = False


def upgrade() -> None:
    # Extend notification_type enum for in-app roster pings.
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'roster_status_ping';"
    )
    # admin_users opt-out flag
    op.execute(
        """
        ALTER TABLE admin_users
          ADD COLUMN IF NOT EXISTS status_pings_opted_out BOOLEAN
            NOT NULL DEFAULT FALSE;
        """
    )

    # roster_status_ping_log — one row per (slot, admin, scheduled_for, channel).
    # Pre-insert with skipped_reason='admin_silenced' / 'event_full_checked_in'
    # is how STOP STATUS + suppression rules deduplicate at the source.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roster_status_ping_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            slot_id UUID NOT NULL REFERENCES specific_date_slots(id) ON DELETE CASCADE,
            admin_user_id UUID NOT NULL REFERENCES admin_users(id),
            scheduled_for TIMESTAMPTZ NOT NULL,
            sent_at TIMESTAMPTZ,
            skipped_reason TEXT,
            channel TEXT NOT NULL,
            CONSTRAINT ck_ping_channel CHECK (
              channel IN ('sms', 'email', 'in_app')
            ),
            CONSTRAINT ck_ping_skipped_reason CHECK (
              skipped_reason IS NULL OR skipped_reason IN (
                'admin_silenced',
                'event_full_checked_in',
                'dispatch_failed',
                'duplicate'
              )
            ),
            UNIQUE (slot_id, admin_user_id, scheduled_for, channel)
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ping_log_slot_scheduled
          ON roster_status_ping_log (slot_id, scheduled_for);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ping_log_tenant_sent
          ON roster_status_ping_log (tenant_id, sent_at DESC)
          WHERE sent_at IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS roster_status_ping_log CASCADE;")
    op.execute(
        """
        ALTER TABLE admin_users
          DROP COLUMN IF EXISTS status_pings_opted_out;
        """
    )
