"""Backfill + lock contacts.{availability,weekly_hours,unavailable_dates} NOT NULL.

The CustomerResponse schema declares these as `list[X] = []`, but the DB
allowed NULL. Pydantic v2 strict-validates None as not-a-list, so any
GET /customers that touched a NULL row returned 500 — surfaced as
"search not working" on the multi-volunteer test tool.

This migration:
  1. Backfills NULL → '[]'::jsonb on the three list-shaped JSONB columns
  2. Sets a server default of '[]'::jsonb so new rows always get []
  3. Locks the columns NOT NULL

Revision ID: a043_contacts_jsonb_not_null
Revises: a042_optin_method_lowercase
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a043_contacts_jsonb_not_null"
down_revision: Union[str, None] = "a042_optin_method_lowercase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = ("availability", "weekly_hours", "unavailable_dates")


def upgrade() -> None:
    for col in COLUMNS:
        op.execute(
            f"UPDATE contacts SET {col} = '[]'::jsonb WHERE {col} IS NULL;"
        )
        op.execute(
            f"ALTER TABLE contacts ALTER COLUMN {col} SET DEFAULT '[]'::jsonb;"
        )
        op.execute(
            f"ALTER TABLE contacts ALTER COLUMN {col} SET NOT NULL;"
        )


def downgrade() -> None:
    for col in COLUMNS:
        op.execute(
            f"ALTER TABLE contacts ALTER COLUMN {col} DROP NOT NULL;"
        )
        op.execute(
            f"ALTER TABLE contacts ALTER COLUMN {col} DROP DEFAULT;"
        )
