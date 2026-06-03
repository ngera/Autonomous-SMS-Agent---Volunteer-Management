"""Extend opt_in_method PG enum with 'ADMIN_AUTOLINK' for the
auto-linked Contact records created when an admin is added (decision #22).

NON-TRANSACTIONAL: ALTER TYPE ... ADD VALUE cannot run inside an
implicit transaction on PostgreSQL ≤11. We disable Alembic's default
transaction wrapping at module level so this migration runs in
AUTOCOMMIT mode.

The new value is not visible to the same transaction that added it
on PG ≤11; backfill that REFERENCES this value lives in the next
migration (a034) so the value is fully committed first.

Revision ID: a033_optinmethod_admin_autolink
Revises: a032_conversation_pending_intent
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a033_optinmethod_admin_autolink"
down_revision: Union[str, None] = "a032_conversation_pending_intent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Disable transactional DDL — required for ALTER TYPE ... ADD VALUE.
transactional_ddl = False


def upgrade() -> None:
    op.execute(
        "ALTER TYPE opt_in_method ADD VALUE IF NOT EXISTS 'admin_autolink';"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values prior to PG 12+
    # via DROP VALUE; rebuilding the type would cascade across all
    # tables using it. Intentional no-op — the enum value is harmless
    # if unused. To truly remove: dump/restore the table.
    pass
