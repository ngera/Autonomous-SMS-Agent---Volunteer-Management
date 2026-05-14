"""Add is_archived flag to contacts.

Revision ID: a023_contact_archived
Revises: a022_appt_type_category_req
Create Date: 2026-05-09

Notes
-----
When admins delete a volunteer who has booking or conversation history we
preserve the audit trail by archiving instead of hard-deleting. Listing
queries hide archived contacts by default; the row stays so historical FKs
keep working.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a023_contact_archived"
down_revision: Union[str, None] = "a022_appt_type_category_req"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE contacts "
        "ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contacts_is_archived "
        "ON contacts(is_archived)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contacts_is_archived")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS is_archived")
