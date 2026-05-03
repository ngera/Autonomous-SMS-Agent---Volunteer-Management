"""Add background_check_required to contacts

Revision ID: a015_background_check_required
Revises: a014_event_location
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a015_background_check_required"
down_revision: Union[str, None] = "a014_event_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS "
        "background_check_required BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS background_check_required")
