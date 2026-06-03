"""Phase 3 — booking_service_log table.

Tracks "what services did this volunteer actually perform during the
event," distinct from booking.appointment_type_id (= what they signed up
for). One booking can produce multiple service_log rows when the
volunteer SWITCHes between services or texts ALSO to add a concurrent
service.

Locked decisions:
  - #29(b): version INT for optimistic concurrency. Every status change
    must include the expected version in its WHERE clause; rowcount=0
    signals supersede race → caller returns "stale, please retry".
  - #17: supersede semantics — when a new pending row arrives while a
    prior pending row exists for the same booking, the prior gets
    status='superseded' (NOT 'rejected') and the new row replaces it.

Also extends notification_type enum with 'service_approval_request'
so admin notifications for SWITCH/ALSO requests can be filtered out
from the regular notifications view.

Revision ID: a039_booking_service_log
Revises: a038_roster_status_ping_log
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a039_booking_service_log"
down_revision: Union[str, None] = "a038_roster_status_ping_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Required for ALTER TYPE ... ADD VALUE on PG ≤11.
transactional_ddl = False


def upgrade() -> None:
    # Extend notification_type enum first (separate from the table
    # because the value needs to be committed before any seed/test
    # inserts can reference it on PG ≤11).
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'service_approval_request';"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS booking_service_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
            appointment_type_id UUID NOT NULL REFERENCES appointment_types(id),
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            version INT NOT NULL DEFAULT 0,
            created_by_admin_id UUID REFERENCES admin_users(id),
            approved_by_admin_id UUID REFERENCES admin_users(id),
            approved_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_bsl_status CHECK (
              status IN ('pending', 'approved', 'rejected', 'superseded')
            ),
            CONSTRAINT ck_bsl_source CHECK (
              source IN ('planned', 'volunteer_sms', 'admin')
            )
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_bsl_booking
          ON booking_service_log (booking_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_bsl_pending
          ON booking_service_log (tenant_id, status)
          WHERE status = 'pending';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS booking_service_log CASCADE;")
    # Notification_type 'service_approval_request' kept (PG doesn't
    # support DROP VALUE on enums prior to 12+).
