"""Add contact_id, contact_phone, tool_calls to token_usage for drill-down

Revision ID: a008_token_usage_drilldown
Revises: a007_token_usage
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a008_token_usage_drilldown"
down_revision: Union[str, None] = "a007_token_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS contact_id UUID REFERENCES contacts(id)")
    op.execute("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(20)")
    op.execute("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS tool_calls JSONB")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_usage_contact_id ON token_usage(contact_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_token_usage_contact_id")
    op.execute("ALTER TABLE token_usage DROP COLUMN IF EXISTS tool_calls")
    op.execute("ALTER TABLE token_usage DROP COLUMN IF EXISTS contact_phone")
    op.execute("ALTER TABLE token_usage DROP COLUMN IF EXISTS contact_id")
