"""Add long-term memory fields to contacts

Revision ID: a012_contact_memory
Revises: a011_suspension_trigger_msg
Create Date: 2026-04-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a012_contact_memory"
down_revision: Union[str, None] = "a011_suspension_trigger_msg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferences JSONB")
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes TEXT")
    op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS memory_updated_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS memory_updated_at")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS notes")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS preferences")
