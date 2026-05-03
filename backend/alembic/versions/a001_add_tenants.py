"""add tenants table and multi-tenant support

Revision ID: a001_add_tenants
Revises: 0d9b21839fe5
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a001_add_tenants"
down_revision: Union[str, None] = "0d9b21839fe5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("business_domain", sa.String(length=255), nullable=False, server_default=sa.text("''")),
        sa.Column("business_timezone", sa.String(length=100), nullable=False, server_default=sa.text("'America/New_York'")),
        sa.Column("admin_panel_url", sa.String(length=500), nullable=False, server_default=sa.text("''")),
        sa.Column("api_domain", sa.String(length=255), nullable=False, server_default=sa.text("''")),
        sa.Column("twilio_account_sid", sa.Text(), nullable=True),
        sa.Column("twilio_auth_token", sa.Text(), nullable=True),
        sa.Column("twilio_phone_number", sa.String(length=20), nullable=True),
        sa.Column("anthropic_api_key", sa.Text(), nullable=True),
        sa.Column("google_client_id", sa.Text(), nullable=True),
        sa.Column("google_client_secret", sa.Text(), nullable=True),
        sa.Column("google_refresh_token", sa.Text(), nullable=True),
        sa.Column("resend_api_key", sa.Text(), nullable=True),
        sa.Column("resend_from_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("twilio_phone_number"),
    )

    # 2. Add SUPER_ADMIN to admin_role enum
    op.execute("ALTER TYPE admin_role ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")

    # 3. Add tenant_id to admin_users (nullable for now — backfilled later)
    op.add_column(
        "admin_users",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
    )
    op.create_index("ix_admin_users_tenant_id", "admin_users", ["tenant_id"])
    op.create_foreign_key(
        "fk_admin_users_tenant_id",
        "admin_users",
        "tenants",
        ["tenant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_admin_users_tenant_id", "admin_users", type_="foreignkey")
    op.drop_index("ix_admin_users_tenant_id", table_name="admin_users")
    op.drop_column("admin_users", "tenant_id")
    op.drop_table("tenants")
    # Note: Cannot remove enum values in PostgreSQL
