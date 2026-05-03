"""Add phone to admin_users and sender_type to conversations

Revision ID: a006_admin_phone_and_sender_type
Revises: a005_tenant_profile_fields
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a006_admin_phone_and_sender_type"
down_revision: Union[str, None] = "a005_tenant_profile_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Admin user phone number for SMS identification
    op.add_column("admin_users", sa.Column("phone", sa.String(20), nullable=True))
    op.create_index(
        "ix_admin_users_tenant_phone",
        "admin_users",
        ["tenant_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    # Conversation sender type (customer or admin)
    op.add_column(
        "conversations",
        sa.Column("sender_type", sa.String(10), server_default="customer", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("conversations", "sender_type")
    op.drop_index("ix_admin_users_tenant_phone", table_name="admin_users")
    op.drop_column("admin_users", "phone")
