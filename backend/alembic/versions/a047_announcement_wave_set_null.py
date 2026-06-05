"""Change announcements.recruitment_wave_id FK to ON DELETE SET NULL.

The previous RESTRICT semantic meant deleting a recruitment_wave
(which cascades from a campaign delete, which cascades from a
specific_date_slot delete) failed whenever the wave had a real
announcement attached — the announcement is the SMS broadcast
record we keep for history, so blocking the delete leaves admins
unable to remove an event whose campaign already fired a wave.

SET NULL is the right semantic: the announcement record survives
(history preserved), but loses its wave back-pointer once the wave
is gone. The column is already nullable so this is a constraint-only
change.

Revision ID: a047_announcement_wave_set_null
Revises: a046_specific_slot_rule_drift
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a047_announcement_wave_set_null"
down_revision: Union[str, None] = "a046_specific_slot_rule_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "announcements_recruitment_wave_id_fkey",
        "announcements",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "announcements_recruitment_wave_id_fkey",
        "announcements",
        "recruitment_waves",
        ["recruitment_wave_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "announcements_recruitment_wave_id_fkey",
        "announcements",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "announcements_recruitment_wave_id_fkey",
        "announcements",
        "recruitment_waves",
        ["recruitment_wave_id"],
        ["id"],
    )
