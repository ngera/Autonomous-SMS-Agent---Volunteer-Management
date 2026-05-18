"""Add recruitment_plan_ready / recruitment_plan_failed to notification_type.

Revision ID: a026_recruit_notif_types
Revises: a025_recruitment_agent
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a026_recruit_notif_types"
down_revision: Union[str, None] = "a025_recruitment_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's Enum column without values_callable inserts the Python
    # enum NAME (uppercase) — that's what the existing rows for this
    # enum use (ACCOUNT_SUSPENDED, NEW_BOOKING, etc.). Add the same case
    # for the recruitment notification types so create_notification works.
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS "
        "'RECRUITMENT_PLAN_READY';"
    )
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS "
        "'RECRUITMENT_PLAN_FAILED';"
    )


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; the values stay. Any rows
    # using them must be removed manually before downgrading.
    pass
