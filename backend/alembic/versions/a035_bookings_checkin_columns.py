"""Phase 1 step 1 — bookings table extensions for check-in/check-out
audit + creation_source.

Adds six new columns covering check-in/out events plus a creation_source
column for analytics (decision #2, #10, #13, plus Row 2 walk-up).

CHECK constraints enforce the value spaces (review-pass #6 + #8):
  - checked_in_source: 5 values (auto_close NOT allowed — there's no
    automated path that auto-checks-in; review-pass issue R6)
  - checked_out_source: 3 values (auto_close IS allowed — T+end+1h job)
  - creation_source: 4 values, defaulting to admin_manual (review-pass
    issue #10 — honest backfill default)

Partial index on (tenant_id, checked_in_at) for run-sheet / Live Events
panel queries (only checked-in rows are interesting).

Revision ID: a035_bookings_checkin_columns
Revises: a034_contact_admin_link
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a035_bookings_checkin_columns"
down_revision: Union[str, None] = "a034_contact_admin_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE bookings
          ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS checked_in_by_id UUID
            REFERENCES admin_users(id),
          ADD COLUMN IF NOT EXISTS checked_in_source TEXT,
          ADD COLUMN IF NOT EXISTS checked_out_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS checked_out_by_id UUID
            REFERENCES admin_users(id),
          ADD COLUMN IF NOT EXISTS checked_out_source TEXT,
          ADD COLUMN IF NOT EXISTS creation_source TEXT
            NOT NULL DEFAULT 'admin_manual';
        """
    )

    # CHECK constraints — distinct value spaces per direction.
    # checked_in_source: NO 'auto_close' (no automated check-in path; R6).
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_bookings_checked_in_source'
          ) THEN
            ALTER TABLE bookings
              ADD CONSTRAINT ck_bookings_checked_in_source CHECK (
                checked_in_source IS NULL OR checked_in_source IN (
                  'volunteer_sms',
                  'volunteer_sms_early',
                  'volunteer_sms_walkup',
                  'admin_override',
                  'admin_initial'
                )
              );
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_bookings_checked_out_source'
          ) THEN
            ALTER TABLE bookings
              ADD CONSTRAINT ck_bookings_checked_out_source CHECK (
                checked_out_source IS NULL OR checked_out_source IN (
                  'volunteer_sms',
                  'admin_override',
                  'auto_close'
                )
              );
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_bookings_creation_source'
          ) THEN
            ALTER TABLE bookings
              ADD CONSTRAINT ck_bookings_creation_source CHECK (
                creation_source IN (
                  'recruiter_wave',
                  'self_signup',
                  'admin_manual',
                  'walk_up'
                )
              );
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_bookings_checked_in_at
          ON bookings (tenant_id, checked_in_at)
          WHERE checked_in_at IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bookings_checked_in_at;")
    op.execute(
        """
        ALTER TABLE bookings
          DROP CONSTRAINT IF EXISTS ck_bookings_creation_source,
          DROP CONSTRAINT IF EXISTS ck_bookings_checked_out_source,
          DROP CONSTRAINT IF EXISTS ck_bookings_checked_in_source,
          DROP COLUMN IF EXISTS creation_source,
          DROP COLUMN IF EXISTS checked_out_source,
          DROP COLUMN IF EXISTS checked_out_by_id,
          DROP COLUMN IF EXISTS checked_out_at,
          DROP COLUMN IF EXISTS checked_in_source,
          DROP COLUMN IF EXISTS checked_in_by_id,
          DROP COLUMN IF EXISTS checked_in_at;
        """
    )
