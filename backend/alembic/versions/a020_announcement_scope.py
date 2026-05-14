"""Add recipient_scope to announcements

Revision ID: a020_announcement_scope
Revises: a019_announcement_event_context
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a020_announcement_scope"
down_revision: Union[str, None] = "a019_announcement_event_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE announcements ADD COLUMN IF NOT EXISTS "
        "recipient_scope VARCHAR(20) NOT NULL DEFAULT 'all'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE announcements DROP COLUMN IF EXISTS recipient_scope")
