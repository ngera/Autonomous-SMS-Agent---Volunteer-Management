"""Add location to availability_rules and specific_date_slots

Revision ID: a014_event_location
Revises: a013_appointment_type_category
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a014_event_location"
down_revision: Union[str, None] = "a013_appointment_type_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE availability_rules ADD COLUMN IF NOT EXISTS location VARCHAR(255)")
    op.execute("ALTER TABLE specific_date_slots ADD COLUMN IF NOT EXISTS location VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE specific_date_slots DROP COLUMN IF EXISTS location")
    op.execute("ALTER TABLE availability_rules DROP COLUMN IF EXISTS location")
