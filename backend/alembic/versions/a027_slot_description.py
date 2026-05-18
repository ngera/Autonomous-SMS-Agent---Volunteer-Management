"""Add description to specific_date_slots.

Revision ID: a027_slot_description
Revises: a026_recruit_notif_types
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a027_slot_description"
down_revision: Union[str, None] = "a026_recruit_notif_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE specific_date_slots "
        "ADD COLUMN IF NOT EXISTS description TEXT;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE specific_date_slots DROP COLUMN IF EXISTS description;"
    )
