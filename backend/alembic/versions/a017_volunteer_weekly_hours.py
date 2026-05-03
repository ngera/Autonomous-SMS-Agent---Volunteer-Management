"""Add weekly_hours and unavailable_dates JSONB to contacts

Revision ID: a017_volunteer_weekly_hours
Revises: a016_volunteer_availability
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a017_volunteer_weekly_hours"
down_revision: Union[str, None] = "a016_volunteer_availability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS weekly_hours JSONB")
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS unavailable_dates JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS unavailable_dates")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS weekly_hours")
