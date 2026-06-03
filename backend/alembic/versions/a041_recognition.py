"""Phase 5 — Recognition (milestones, badges, awards).

Two tables + three partial unique indexes that together implement
decision #27's hybrid uniqueness scopes (lifetime / per_event / per_period).

  award_definition       : the template (kind, key, label, auto_criteria, scope)
  volunteer_recognition  : the earning event (contact, definition, when, scope-context)

Uniqueness enforcement:
  - lifetime: one (contact, definition) ever. UNIQUE where period_key IS NULL
    AND earned_via_slot_id IS NULL.
  - per_event: one (contact, definition, slot). UNIQUE where earned_via_slot_id IS NOT NULL.
  - per_period: one (contact, definition, period_key). UNIQUE where period_key IS NOT NULL.

The recognition engine writes the appropriate column(s) based on the
definition's uniqueness_scope; the partial index for that scope
enforces dedup via ON CONFLICT DO NOTHING.

Revision ID: a041_recognition
Revises: a040_booking_review
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a041_recognition"
down_revision: Union[str, None] = "a040_booking_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── award_definition ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS award_definition (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            icon_key TEXT,
            auto_criteria JSONB,
            uniqueness_scope TEXT NOT NULL DEFAULT 'lifetime',
            period_unit TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_award_definition_tenant_key UNIQUE (tenant_id, key),
            CONSTRAINT ck_award_definition_kind
              CHECK (kind IN ('milestone', 'badge', 'award')),
            CONSTRAINT ck_award_definition_uniqueness_scope
              CHECK (uniqueness_scope IN ('lifetime', 'per_event', 'per_period')),
            CONSTRAINT ck_award_definition_period_unit
              CHECK (
                (uniqueness_scope = 'per_period' AND period_unit IS NOT NULL)
                OR
                (uniqueness_scope != 'per_period' AND period_unit IS NULL)
              ),
            CONSTRAINT ck_award_definition_period_unit_value
              CHECK (period_unit IS NULL OR period_unit IN ('month', 'quarter', 'year'))
        );
        """
    )

    # ── volunteer_recognition ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteer_recognition (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            definition_id UUID NOT NULL REFERENCES award_definition(id) ON DELETE CASCADE,
            earned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            earned_via_review_id UUID REFERENCES booking_review(id) ON DELETE SET NULL,
            earned_via_slot_id UUID REFERENCES specific_date_slots(id) ON DELETE SET NULL,
            period_key TEXT,
            granted_by_admin_id UUID REFERENCES admin_users(id),
            notes TEXT
        );
        """
    )

    # Tenant-scoped lookup index for Phase 5 observability rollups.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recognition_tenant_earned_at
          ON volunteer_recognition (tenant_id, earned_at DESC);
        """
    )

    # Per-contact lookup (Recognition tab on contact detail page).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recognition_contact
          ON volunteer_recognition (contact_id, earned_at DESC);
        """
    )

    # Three partial unique indexes (decision #27).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_recog_lifetime
          ON volunteer_recognition (contact_id, definition_id)
          WHERE period_key IS NULL AND earned_via_slot_id IS NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_recog_per_event
          ON volunteer_recognition (contact_id, definition_id, earned_via_slot_id)
          WHERE earned_via_slot_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_recog_per_period
          ON volunteer_recognition (contact_id, definition_id, period_key)
          WHERE period_key IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS volunteer_recognition CASCADE;")
    op.execute("DROP TABLE IF EXISTS award_definition CASCADE;")
