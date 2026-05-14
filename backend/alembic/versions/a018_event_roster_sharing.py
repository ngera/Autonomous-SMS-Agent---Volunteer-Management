"""Add roster sharing fields to events and bookings

Revision ID: a018_event_roster_sharing
Revises: a017_volunteer_weekly_hours
Create Date: 2026-05-03

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a018_event_roster_sharing"
down_revision: Union[str, None] = "a017_volunteer_weekly_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE availability_rules ADD COLUMN IF NOT EXISTS "
        "allow_roster_sharing BOOLEAN NOT NULL DEFAULT true"
    )
    op.execute(
        "ALTER TABLE specific_date_slots ADD COLUMN IF NOT EXISTS "
        "allow_roster_sharing BOOLEAN NOT NULL DEFAULT true"
    )
    op.execute(
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS "
        "roster_visibility VARCHAR(20) NOT NULL DEFAULT 'first_name'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS roster_visibility")
    op.execute("ALTER TABLE specific_date_slots DROP COLUMN IF EXISTS allow_roster_sharing")
    op.execute("ALTER TABLE availability_rules DROP COLUMN IF EXISTS allow_roster_sharing")
