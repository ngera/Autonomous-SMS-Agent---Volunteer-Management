"""Track when a materialized slot's parent rule has drifted away from
the slot's own current values.

When an admin edits an AvailabilityRule, the propagation engine fans
out the new values to materialized slots that are "safe" (no
bookings, no active campaign) and silently overwrites them. For
unsafe slots — where pushing rule changes would silently move a slot
volunteers already booked into — the engine instead stashes the
diff on the slot itself and surfaces a "Rule changed — review this
slot" alert on the dashboard. The admin then chooses to accept the
drift (apply rule values) or ignore it (resolve in place).

Columns added to specific_date_slots:

  - rule_drift_at        : timestamptz, the moment the rule edit happened
                            that this slot couldn't safely absorb. NULL
                            once the drift is resolved.
  - rule_drift_summary   : jsonb list of {"field", "from", "to"} entries
                            describing the changes the alert should show.

The dashboard alerts feed (_alerts_rule_changed) filters on
rule_drift_at IS NOT NULL.

Revision ID: a046_specific_slot_rule_drift
Revises: a045_specific_slot_rule_link
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a046_specific_slot_rule_drift"
down_revision: Union[str, None] = "a045_specific_slot_rule_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "specific_date_slots",
        sa.Column(
            "rule_drift_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "specific_date_slots",
        sa.Column(
            "rule_drift_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    # Partial index — the alert query only cares about rows with an
    # unresolved drift, which is a tiny fraction of the table.
    op.create_index(
        "ix_specific_date_slots_drift",
        "specific_date_slots",
        ["tenant_id", "rule_drift_at"],
        postgresql_where=sa.text("rule_drift_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_specific_date_slots_drift",
        table_name="specific_date_slots",
    )
    op.drop_column("specific_date_slots", "rule_drift_summary")
    op.drop_column("specific_date_slots", "rule_drift_at")
