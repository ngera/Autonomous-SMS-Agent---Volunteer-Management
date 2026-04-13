"""Add token_usage table for AI token consumption tracking

Revision ID: a007_token_usage
Revises: a006_admin_phone_and_sender_type
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a007_token_usage"
down_revision: Union[str, None] = "a006_admin_phone_and_sender_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE token_usage_source AS ENUM ('conversation', 'screener', 'test_tool');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            source token_usage_source NOT NULL,
            model VARCHAR(100) NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            conversation_id UUID REFERENCES conversations(id),
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_token_usage_tenant_id ON token_usage(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_usage_created_at ON token_usage(created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS token_usage")
    op.execute("DROP TYPE IF EXISTS token_usage_source")
