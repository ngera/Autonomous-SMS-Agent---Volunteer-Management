"""Normalize opt_in_method PG enum values to lowercase.

Before:  SMS_REPLY, ADMIN_MANUAL, IMPORTED, admin_autolink
After:   sms_reply, admin_manual, imported, admin_autolink

Existing rows keep their identity (PG enums are stored by oid; RENAME VALUE
only renames the label). The companion model change in
[contact_consent.py] sets `values_callable` so SQLAlchemy serializes by
`.value` (lowercase) rather than `.name` (uppercase).

Revision ID: a042_optin_method_lowercase
Revises: a041_recognition
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a042_optin_method_lowercase"
down_revision: Union[str, None] = "a041_recognition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'SMS_REPLY' TO 'sms_reply';")
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'ADMIN_MANUAL' TO 'admin_manual';")
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'IMPORTED' TO 'imported';")


def downgrade() -> None:
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'sms_reply' TO 'SMS_REPLY';")
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'admin_manual' TO 'ADMIN_MANUAL';")
    op.execute("ALTER TYPE opt_in_method RENAME VALUE 'imported' TO 'IMPORTED';")
