"""Add 'walkup_candidate' value to notification_type PG enum.

Row 4 admin notifications need a distinct NotificationType so they
can be filtered out / dispatched to the Needs Attention panel
candidates section. Non-transactional ALTER TYPE per the pattern
established in a033.

Revision ID: a037_notification_walkup_candidate
Revises: a036_volunteer_candidate
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a037_notification_walkup_candidate"
down_revision: Union[str, None] = "a036_volunteer_candidate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

transactional_ddl = False


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'walkup_candidate';"
    )


def downgrade() -> None:
    # Postgres < 12 doesn't support DROP VALUE; intentional no-op.
    pass
