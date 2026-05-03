"""Add label column to availability_rules

Revision ID: a003_availability_label
Revises: a002_multi_tenant
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a003_availability_label"
down_revision: Union[str, None] = "a002_multi_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "availability_rules",
        sa.Column("label", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("availability_rules", "label")
