"""Add all_services_enabled to contacts

Revision ID: a009_contact_all_services
Revises: a008_token_usage_drilldown
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a009_contact_all_services"
down_revision: Union[str, None] = "a008_token_usage_drilldown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS all_services_enabled BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS all_services_enabled")
