"""Add default_roster_visibility column to contacts so the volunteer's
chosen roster visibility (first_name / full_name / hidden) sticks for
all forthcoming bookings — no re-asking on every new sign-up.

Nullable on purpose: NULL means "not yet chosen" and book_appointment
falls back to first_name (existing default behavior) while still asking
the volunteer once. Once set, the saved value drives the default for
future bookings.

Revision ID: a031_contact_roster_default
Revises: a030_agent_architecture
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a031_contact_roster_default"
down_revision: Union[str, None] = "a030_agent_architecture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contacts
          ADD COLUMN IF NOT EXISTS default_roster_visibility VARCHAR(20);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE contacts
          DROP COLUMN IF EXISTS default_roster_visibility;
        """
    )
