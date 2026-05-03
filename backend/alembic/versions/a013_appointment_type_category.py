"""Add category column to appointment_types

Revision ID: a013_appointment_type_category
Revises: a012_contact_memory
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a013_appointment_type_category"
down_revision: Union[str, None] = "a012_contact_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE appointment_types ADD COLUMN IF NOT EXISTS category VARCHAR(100)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_appointment_types_category "
        "ON appointment_types (category)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_appointment_types_category")
    op.execute("ALTER TABLE appointment_types DROP COLUMN IF EXISTS category")
