"""Link specific_date_slots back to the recurring rule they were
materialized from.

When an admin clicks "Start Campaign" on a recurring event instance, the
system promotes that one occurrence into a real SpecificDateSlot so a
campaign can attach to it (campaigns require event_slot_id). This
column records the provenance — which AvailabilityRule the slot was
spawned from — so the system can:

  1. Auto-propagate rule edits to materialized slots that are still
     "safe" (no bookings, no active campaign). See dashboard rule-edit
     hook in Phase B.
  2. Show "Materialized from ..." in the slot detail page.
  3. Surface "Rule changed — review this slot" alerts when a rule edit
     hits a slot that has bookings or a live campaign.

`ON DELETE SET NULL`: if the rule is deleted, materialized slots
survive as standalone specific events with the FK nulled out.
Provenance is gone, but bookings/campaigns/reviews remain intact.

Revision ID: a045_specific_slot_rule_link
Revises: a044_dashboard_alert_state
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a045_specific_slot_rule_link"
down_revision: Union[str, None] = "a044_dashboard_alert_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "specific_date_slots",
        sa.Column(
            "availability_rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("availability_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_specific_date_slots_rule_id",
        "specific_date_slots",
        ["availability_rule_id"],
    )
    # Idempotency guard: prevent two materialized slots for the same
    # (rule, date) pair. Lets the materialize service safely re-call
    # without creating duplicates if two admins click at once.
    op.create_index(
        "ux_specific_date_slots_rule_date",
        "specific_date_slots",
        ["availability_rule_id", "date"],
        unique=True,
        postgresql_where=sa.text("availability_rule_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_specific_date_slots_rule_date",
        table_name="specific_date_slots",
    )
    op.drop_index(
        "ix_specific_date_slots_rule_id",
        table_name="specific_date_slots",
    )
    op.drop_column("specific_date_slots", "availability_rule_id")
