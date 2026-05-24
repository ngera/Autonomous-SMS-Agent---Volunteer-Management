"""Relax recruitment_waves.announcement_id FK to ON DELETE SET NULL.

Today the FK has no ON DELETE clause (= NO ACTION = RESTRICT), so
deleting a SENT announcement created by the recruiter fails with a
foreign-key violation. Admin Announcements page now offers a "delete
specific announcement" action regardless of status; this migration
makes that action safe by NULL-ing the wave's announcement_id rather
than blocking the delete.

The wave row itself is preserved (it's permanent audit of the send);
only the back-link to the deleted announcement row is dropped.

Revision ID: a029_announcement_delete_cascade
Revises: a028_booking_event_slot_link
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a029_announcement_delete_cascade"
down_revision: Union[str, None] = "a028_booking_event_slot_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop and recreate the FK with ON DELETE SET NULL. Postgres's
    # ALTER CONSTRAINT can't change the action in a single statement.
    op.execute(
        """
        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            SELECT conname INTO constraint_name
            FROM pg_constraint
            WHERE conrelid = 'recruitment_waves'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) ILIKE '%REFERENCES announcements%';
            IF constraint_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE recruitment_waves DROP CONSTRAINT %I',
                    constraint_name
                );
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE recruitment_waves
          ADD CONSTRAINT fk_recruitment_waves_announcement
          FOREIGN KEY (announcement_id)
          REFERENCES announcements(id)
          ON DELETE SET NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE recruitment_waves "
        "DROP CONSTRAINT IF EXISTS fk_recruitment_waves_announcement;"
    )
    op.execute(
        """
        ALTER TABLE recruitment_waves
          ADD CONSTRAINT recruitment_waves_announcement_id_fkey
          FOREIGN KEY (announcement_id)
          REFERENCES announcements(id);
        """
    )
