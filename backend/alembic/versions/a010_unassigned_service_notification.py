"""Add unassigned_service to notification_type enum

Revision ID: a010_unassigned_service_notification
Revises: a009_contact_all_services
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a010_unassigned_svc_notif"
down_revision: Union[str, None] = "a009_contact_all_services"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'unassigned_service'")


def downgrade() -> None:
    pass  # Cannot remove enum values in PostgreSQL
