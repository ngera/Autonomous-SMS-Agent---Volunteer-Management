"""Track changes to a contact's saved roster-visibility preference.

When a volunteer says "show my first name" / "use my full name" /
"hide me" during a booking and that explicit pick differs from their
saved default, we record the transition here so an admin can see when
and how their stated preference shifted.

Scoped to roster_visibility today (the only preference users mutate
this way), but the table is shaped to absorb future single-value
preferences (notification cadence, language, etc.) under a `field`
discriminator without another migration.

Revision ID: a048_contact_preference_history
Revises: a047_announcement_wave_set_null
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a048_contact_preference_history"
down_revision: Union[str, None] = "a047_announcement_wave_set_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_preference_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("previous_value", sa.String(64), nullable=True),
        sa.Column("new_value", sa.String(64), nullable=False),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="user_sms",
        ),
        sa.Column(
            "source_booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_contact_preference_history_contact_field",
        "contact_preference_history",
        ["contact_id", "field"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contact_preference_history_contact_field",
        table_name="contact_preference_history",
    )
    op.drop_table("contact_preference_history")
