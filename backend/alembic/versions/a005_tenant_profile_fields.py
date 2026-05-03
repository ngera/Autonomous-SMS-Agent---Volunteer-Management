"""Add tenant profile, billing, contact fields and pause status

Revision ID: a005_tenant_profile_fields
Revises: a004_customer_sex_and_prefs
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a005_tenant_profile_fields"
down_revision: Union[str, None] = "a004_customer_sex_and_prefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Contact preference enum
    contact_pref_enum = sa.Enum("email", "phone", "sms", name="contact_preference", schema=None)
    contact_pref_enum.create(op.get_bind(), checkfirst=True)

    # Store info
    op.add_column("tenants", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("address_street", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("address_city", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("address_state", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("address_zip", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("address_country", sa.String(100), nullable=True))

    # Billing info
    op.add_column("tenants", sa.Column("billing_email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("billing_address_street", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("billing_address_city", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("billing_address_state", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("billing_address_zip", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("billing_address_country", sa.String(100), nullable=True))

    # Primary contact
    op.add_column("tenants", sa.Column("contact_name", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("contact_preference", contact_pref_enum, nullable=True))

    # Pause / deactivate timestamps
    op.add_column("tenants", sa.Column("is_paused", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("tenants", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "deactivated_at")
    op.drop_column("tenants", "paused_at")
    op.drop_column("tenants", "is_paused")
    op.drop_column("tenants", "contact_preference")
    op.drop_column("tenants", "contact_email")
    op.drop_column("tenants", "contact_phone")
    op.drop_column("tenants", "contact_name")
    op.drop_column("tenants", "billing_address_country")
    op.drop_column("tenants", "billing_address_zip")
    op.drop_column("tenants", "billing_address_state")
    op.drop_column("tenants", "billing_address_city")
    op.drop_column("tenants", "billing_address_street")
    op.drop_column("tenants", "billing_email")
    op.drop_column("tenants", "address_country")
    op.drop_column("tenants", "address_zip")
    op.drop_column("tenants", "address_state")
    op.drop_column("tenants", "address_city")
    op.drop_column("tenants", "address_street")
    op.drop_column("tenants", "email")
    op.drop_column("tenants", "phone")

    sa.Enum(name="contact_preference").drop(op.get_bind(), checkfirst=True)
