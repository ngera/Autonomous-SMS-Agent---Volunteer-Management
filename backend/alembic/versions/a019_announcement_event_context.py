"""Add event_context JSONB to announcements

Revision ID: a019_announcement_event_context
Revises: a018_event_roster_sharing
Create Date: 2026-05-03

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a019_announcement_event_context"
down_revision: Union[str, None] = "a018_event_roster_sharing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE announcements ADD COLUMN IF NOT EXISTS event_context JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE announcements DROP COLUMN IF EXISTS event_context")
