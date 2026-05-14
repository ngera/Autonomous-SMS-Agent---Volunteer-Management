"""Unique index on appointment_types (tenant_id, name, category, duration_minutes)

Revision ID: a021_appt_type_unique
Revises: a020_announcement_scope
Create Date: 2026-05-09

Notes
-----
Postgres treats NULL as not-equal-to-NULL in regular UNIQUE constraints, so a
UNIQUE on a nullable `category` column would still allow two rows with the same
(tenant_id, name, NULL, duration_minutes). Use a partial-style expression index
with COALESCE so NULL is treated as equivalent to an empty string.

If the table already contains duplicates the index creation will fail; the
operator will need to dedupe manually. Run this query to find offenders:

    SELECT tenant_id, name, COALESCE(category, ''), duration_minutes, COUNT(*)
    FROM appointment_types
    GROUP BY tenant_id, name, COALESCE(category, ''), duration_minutes
    HAVING COUNT(*) > 1;
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a021_appt_type_unique"
down_revision: Union[str, None] = "a020_announcement_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_appointment_types_tenant_name_category_duration "
        "ON appointment_types "
        "(tenant_id, name, COALESCE(category, ''), duration_minutes)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_appointment_types_tenant_name_category_duration"
    )
