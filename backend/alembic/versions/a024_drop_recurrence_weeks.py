"""Drop appointment_types.recurrence_weeks_default.

Revision ID: a024_drop_recurrence_weeks
Revises: a023_contact_archived
Create Date: 2026-05-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a024_drop_recurrence_weeks"
down_revision: Union[str, None] = "a023_contact_archived"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE appointment_types DROP COLUMN IF EXISTS recurrence_weeks_default"
    )


def downgrade() -> None:
    op.add_column(
        "appointment_types",
        sa.Column("recurrence_weeks_default", sa.Integer(), nullable=True),
    )
