"""Add availability JSONB array to contacts

Revision ID: a016_volunteer_availability
Revises: a015_background_check_required
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a016_volunteer_availability"
down_revision: Union[str, None] = "a015_background_check_required"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS availability JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS availability")
