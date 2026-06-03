"""Per-tenant snooze + dismiss state for the redesigned Needs-You-Now feed.

Phase 1 stored snoozes / dismissals in browser localStorage so the
structural redesign could ship without a backend table. Phase 2 promotes
that state to a server-side table so:
  - Snoozes / dismissals survive browser refresh + device switch.
  - Multiple admins on the same tenant share one inbox — if Alice
    dismisses an alert, Bob doesn't see it either.
  - We can record dismiss reasons for product-iteration signal.

Uniqueness scope is (tenant_id, alert_id). Re-snoozing or re-dismissing
the same alert upserts via ON CONFLICT — the latest action wins.

Revision ID: a044_dashboard_alert_state
Revises: a043_contacts_jsonb_not_null
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a044_dashboard_alert_state"
down_revision: Union[str, None] = "a043_contacts_jsonb_not_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_alert_state",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"), nullable=False,
        ),
        sa.Column("alert_id", sa.String(255), nullable=False),
        # 'snoozed' or 'dismissed' — stored as text + CHECK so we can
        # extend without an enum migration.
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismiss_reason", sa.Text, nullable=True),
        sa.Column(
            "created_by_admin_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admin_users.id"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "alert_id",
                            name="uq_dashboard_alert_state_tenant_alert"),
    )
    op.create_index(
        "ix_dashboard_alert_state_tenant_id",
        "dashboard_alert_state", ["tenant_id"],
    )
    op.execute(
        "ALTER TABLE dashboard_alert_state "
        "ADD CONSTRAINT ck_dashboard_alert_state_state "
        "CHECK (state IN ('snoozed', 'dismissed'));"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_alert_state_tenant_id",
        table_name="dashboard_alert_state",
    )
    op.drop_table("dashboard_alert_state")
