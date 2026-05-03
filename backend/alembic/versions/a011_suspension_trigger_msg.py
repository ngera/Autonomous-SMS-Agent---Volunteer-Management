"""Add triggering_message to contact_suspensions

Revision ID: a011_suspension_trigger_msg
Revises: a010_unassigned_svc_notif
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a011_suspension_trigger_msg"
down_revision: Union[str, None] = "a010_unassigned_svc_notif"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contact_suspensions ADD COLUMN IF NOT EXISTS triggering_message TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE contact_suspensions DROP COLUMN IF EXISTS triggering_message")
