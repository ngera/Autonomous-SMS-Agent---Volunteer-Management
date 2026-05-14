"""Make appointment_types.category required (NOT NULL).

Revision ID: a022_appt_type_category_req
Revises: a021_appt_type_unique
Create Date: 2026-05-09

Notes
-----
Backfills any pre-existing rows whose category is NULL or blank with
'Uncategorized' so the NOT NULL constraint can apply, then rebuilds the
tenant/name/category/duration unique index without the COALESCE wrapper since
NULL is no longer reachable.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a022_appt_type_category_req"
down_revision: Union[str, None] = "a021_appt_type_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill NULL / blank categories so NOT NULL can apply.
    op.execute(
        "UPDATE appointment_types "
        "SET category = 'Uncategorized' "
        "WHERE category IS NULL OR TRIM(category) = ''"
    )
    op.execute(
        "ALTER TABLE appointment_types "
        "ALTER COLUMN category SET NOT NULL"
    )

    # Rebuild the unique index without COALESCE — pure-column form is simpler
    # and identical now that category is NOT NULL.
    op.execute(
        "DROP INDEX IF EXISTS uq_appointment_types_tenant_name_category_duration"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_appointment_types_tenant_name_category_duration "
        "ON appointment_types (tenant_id, name, category, duration_minutes)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_appointment_types_tenant_name_category_duration"
    )
    op.execute(
        "ALTER TABLE appointment_types "
        "ALTER COLUMN category DROP NOT NULL"
    )
    # Restore the COALESCE form for the previous revision.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_appointment_types_tenant_name_category_duration "
        "ON appointment_types "
        "(tenant_id, name, COALESCE(category, ''), duration_minutes)"
    )
