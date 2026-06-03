"""Admin-Contact auto-link (decision #22) + recruiting opt-out (decision #30).

Two-part schema change:
  - contacts.admin_user_id UUID UNIQUE FK to admin_users (per-tenant
    enforced via existing UNIQUE constraint on Contact)
  - contacts.exclude_from_recruiting BOOLEAN DEFAULT FALSE

Backfill: every existing admin_users row where role != SUPER_ADMIN
gets a linked Contact:
  - If Contact already exists at (tenant_id, phone) → link via FK
  - Else → create Contact (name/phone/email from admin) +
    ContactConsent(OPTED_IN, admin_autolink) + link via FK
  - In all cases set exclude_from_recruiting=TRUE (decision #30)

Pre-Phase-1 features (CHECKIN ME, admin-as-volunteer, RESERVE) assume
this is complete.

Revision ID: a034_contact_admin_link
Revises: a033_optinmethod_admin_autolink
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a034_contact_admin_link"
down_revision: Union[str, None] = "a033_optinmethod_admin_autolink"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema additions
    op.execute(
        """
        ALTER TABLE contacts
          ADD COLUMN IF NOT EXISTS admin_user_id UUID
            REFERENCES admin_users(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS exclude_from_recruiting BOOLEAN
            NOT NULL DEFAULT FALSE;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_contacts_admin_user_id
          ON contacts (admin_user_id)
          WHERE admin_user_id IS NOT NULL;
        """
    )

    # Backfill: link or create Contact for each admin_users row (except SUPER_ADMIN).
    # Step 1: link existing Contacts that share (tenant_id, phone) with an admin.
    op.execute(
        """
        UPDATE contacts c
        SET admin_user_id = a.id,
            exclude_from_recruiting = TRUE
        FROM admin_users a
        WHERE a.role::text != 'SUPER_ADMIN'
          AND a.is_active = TRUE
          AND a.phone IS NOT NULL
          AND a.tenant_id = c.tenant_id
          AND a.phone = c.phone
          AND c.admin_user_id IS NULL;
        """
    )

    # Step 2: create Contacts for admins who don't have one yet.
    op.execute(
        """
        INSERT INTO contacts (
            id, tenant_id, phone, name, email,
            status, all_services_enabled, background_check_required,
            is_archived, admin_user_id, exclude_from_recruiting,
            reminder_preference_days,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            a.tenant_id,
            a.phone,
            COALESCE(SPLIT_PART(a.email, '@', 1), 'Admin'),
            a.email,
            'ACTIVE',
            TRUE,
            FALSE,
            FALSE,
            a.id,
            TRUE,
            1,
            NOW(),
            NOW()
        FROM admin_users a
        WHERE a.role::text != 'SUPER_ADMIN'
          AND a.is_active = TRUE
          AND a.phone IS NOT NULL
          AND a.tenant_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM contacts c2
            WHERE c2.admin_user_id = a.id
          );
        """
    )

    # Step 3: create ContactConsent (OPTED_IN, admin_autolink) for any
    # newly-linked Contact that doesn't already have a consent row.
    op.execute(
        """
        INSERT INTO contact_consent (
            id, tenant_id, contact_id, contact_phone,
            status, opt_in_method, opted_in_at
        )
        SELECT
            gen_random_uuid(),
            c.tenant_id,
            c.id,
            c.phone,
            'OPTED_IN',
            'admin_autolink',
            NOW()
        FROM contacts c
        WHERE c.admin_user_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM contact_consent cc
            WHERE cc.contact_id = c.id
          );
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_contacts_admin_user_id;")
    op.execute(
        """
        ALTER TABLE contacts
          DROP COLUMN IF EXISTS exclude_from_recruiting,
          DROP COLUMN IF EXISTS admin_user_id;
        """
    )
