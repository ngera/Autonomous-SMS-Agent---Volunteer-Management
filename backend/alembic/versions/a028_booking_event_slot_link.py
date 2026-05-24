"""Link bookings to specific_date_slots + pending-reconfirmation flag.

Adds two nullable columns on bookings:
- event_slot_id (FK to specific_date_slots, ON DELETE SET NULL) — explicit
  link from a signup to its event. Was previously implicit via
  tenant_id + appointment_type_id + scheduled_at, which silently broke
  when an admin moved a slot's date (orphan bookings at the old date,
  empty roster at the new date).
- pending_reconfirmation_until — timestamp set when the slot date or
  time changes; the booked volunteer is asked to confirm or opt out
  before this expires.

Backfill is best-effort: match by tenant + service + slot.date with
service_config containing the booking's appointment_type. Bookings that
don't match any slot (regular-availability bookings) stay NULL — that's
correct, they're not event signups.

Revision ID: a028_booking_event_slot_link
Revises: a027_slot_description
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a028_booking_event_slot_link"
down_revision: Union[str, None] = "a027_slot_description"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. New notification type for the rescheduling cascade. Same shape
    #    as a026's recruitment notif types — uppercase enum NAME because
    #    SQLAlchemy's default Enum mapping uses Python enum member names.
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS "
        "'EVENT_RESCHEDULED';"
    )

    # 1. Add the new columns (nullable so the migration is online-safe).
    op.execute(
        """
        ALTER TABLE bookings
          ADD COLUMN IF NOT EXISTS event_slot_id UUID NULL,
          ADD COLUMN IF NOT EXISTS pending_reconfirmation_until TIMESTAMPTZ NULL;
        """
    )

    # 2. FK with ON DELETE SET NULL — deleting an event nulls the link
    #    on its bookings rather than cascading the delete, so booking
    #    history stays intact.
    op.execute(
        """
        ALTER TABLE bookings
          ADD CONSTRAINT fk_bookings_event_slot
          FOREIGN KEY (event_slot_id)
          REFERENCES specific_date_slots(id)
          ON DELETE SET NULL;
        """
    )

    # 3. Partial index — most bookings won't have a slot link (regular
    #    weekly availability bookings), so a partial index keeps the
    #    btree small.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_bookings_event_slot
          ON bookings (event_slot_id)
          WHERE event_slot_id IS NOT NULL;
        """
    )

    # 4. Best-effort backfill. Match by tenant + service_config
    #    containment + same date. Time-window check is intentionally
    #    skipped — a booking and its slot share a date and service is
    #    enough to identify the link for existing data.
    op.execute(
        """
        UPDATE bookings b
        SET event_slot_id = s.id
        FROM specific_date_slots s
        WHERE b.event_slot_id IS NULL
          AND b.tenant_id = s.tenant_id
          AND DATE(b.scheduled_at AT TIME ZONE 'UTC') = s.date
          AND s.service_config IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(s.service_config) entry
            WHERE (entry->>'appointment_type_id')::uuid
                = b.appointment_type_id
          );
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bookings_event_slot;")
    op.execute(
        "ALTER TABLE bookings DROP CONSTRAINT IF EXISTS fk_bookings_event_slot;"
    )
    op.execute(
        """
        ALTER TABLE bookings
          DROP COLUMN IF EXISTS event_slot_id,
          DROP COLUMN IF EXISTS pending_reconfirmation_until;
        """
    )
