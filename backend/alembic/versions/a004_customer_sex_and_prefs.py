"""Add customer sex, preferred appointment types, and announcements

Revision ID: a004_customer_sex_and_prefs
Revises: a003_availability_label
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, UUID, JSON

revision: str = "a004_customer_sex_and_prefs"
down_revision: Union[str, None] = "a003_availability_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create contact_sex enum and add sex column to contacts
    contact_sex_enum = sa.Enum(
        "male", "female", "non_binary", "prefer_not_to_say",
        name="contact_sex",
    )
    contact_sex_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "contacts",
        sa.Column("sex", contact_sex_enum, nullable=True),
    )

    # 2. Create contact_preferred_types join table
    op.create_table(
        "contact_preferred_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("appointment_type_id", UUID(as_uuid=True), sa.ForeignKey("appointment_types.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("tenant_id", "contact_id", "appointment_type_id", name="uq_contact_preferred_type"),
    )

    # 3. Create announcement_status enum and announcements table
    _announcement_status_values = ("draft", "scheduled", "sending", "sent", "failed")
    _announcement_status_named = sa.Enum(
        *_announcement_status_values,
        name="announcement_status",
    )
    _announcement_status_named.create(op.get_bind(), checkfirst=True)
    announcement_status_col = PG_ENUM(
        *_announcement_status_values,
        name="announcement_status",
        create_type=False,
    )
    op.create_table(
        "announcements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("filter_appointment_type_ids", JSON, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", announcement_status_col, nullable=False, server_default="draft"),
        sa.Column("total_recipients", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by_admin_id", UUID(as_uuid=True), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("announcements")
    sa.Enum(name="announcement_status").drop(op.get_bind(), checkfirst=True)
    op.drop_table("contact_preferred_types")
    op.drop_column("contacts", "sex")
    sa.Enum(name="contact_sex").drop(op.get_bind(), checkfirst=True)
