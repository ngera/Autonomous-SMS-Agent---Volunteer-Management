"""Phase 4 — booking_review table + contacts.historical_quality_* columns.

Two auto-creation paths land rows here:
  - T+start+30min — no_show review for bookings with no check-in (#14)
  - T+end + review_grace_minutes — pending review for everyone else (#5)

Admin approves with grade 1-5 (or marks skipped / leaves no_show as-is).
On approval, contacts.historical_quality_score is recomputed (decay-weighted
average over last N grades) and the recruiter targeting layer uses it as a
soft weight (decision #24).

Unlock policy (decision #16): SUPER_ADMIN always; OWNER unlimited within
24h of slot.end_at. unlock_count increments atomically alongside
unlocked_at / unlocked_by_admin_id (R2).

Hours derivation (decision #10): segments JSONB array reconstructed from
agent_call_log at approval time. Early-check-in floor applies to the first
segment only.

Revision ID: a040_booking_review
Revises: a039_booking_service_log
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a040_booking_review"
down_revision: Union[str, None] = "a039_booking_service_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-contact historical quality cache (decision #8 + #24).
    op.execute(
        """
        ALTER TABLE contacts
          ADD COLUMN IF NOT EXISTS historical_quality_score NUMERIC(3,2),
          ADD COLUMN IF NOT EXISTS historical_quality_updated_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS approved_reviews_count INT
            NOT NULL DEFAULT 0;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS booking_review (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            booking_id UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending',
            grade SMALLINT,
            grade_notes TEXT,
            total_hours NUMERIC(5,2),
            segments JSONB,
            final_check_in_at TIMESTAMPTZ,
            final_check_out_at TIMESTAMPTZ,
            reviewed_by_admin_id UUID REFERENCES admin_users(id),
            reviewed_at TIMESTAMPTZ,
            unlocked_at TIMESTAMPTZ,
            unlocked_by_admin_id UUID REFERENCES admin_users(id),
            unlock_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_review_status CHECK (
              status IN ('pending', 'approved', 'no_show', 'skipped')
            ),
            CONSTRAINT ck_review_grade CHECK (
              grade IS NULL OR (grade BETWEEN 1 AND 5)
            )
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_review_pending
          ON booking_review (tenant_id, status)
          WHERE status = 'pending';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_review_tenant_status_reviewed
          ON booking_review (tenant_id, status, reviewed_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS booking_review CASCADE;")
    op.execute(
        """
        ALTER TABLE contacts
          DROP COLUMN IF EXISTS approved_reviews_count,
          DROP COLUMN IF EXISTS historical_quality_updated_at,
          DROP COLUMN IF EXISTS historical_quality_score;
        """
    )
