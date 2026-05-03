"""multi-tenant schema: contact PK change, tenant_id on all tables, system_setting PK change

Revision ID: a002_multi_tenant
Revises: a001_add_tenants
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a002_multi_tenant"
down_revision: Union[str, None] = "a001_add_tenants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =============================================
    # STEP 1: Add tenant_id to all non-contact tables (nullable initially)
    # =============================================
    tables_needing_tenant_id = [
        "appointment_types",
        "related_services",
        "bookings",
        "booking_history",
        "availability_rules",
        "blocked_dates",
        "conversations",
        "contact_strikes",
        "contact_suspensions",
        "customer_appointment_patterns",
        "reminders",
        "admin_notifications",
        "contact_consent",
        "contact_consent_history",
    ]
    for table in tables_needing_tenant_id:
        op.add_column(table, sa.Column("tenant_id", sa.UUID(), nullable=True))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    # =============================================
    # STEP 2: Contact table — add id, tenant_id columns
    # =============================================
    op.add_column("contacts", sa.Column("id", sa.UUID(), nullable=True, server_default=sa.text("gen_random_uuid()")))
    op.add_column("contacts", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])

    # Backfill contact IDs
    op.execute("UPDATE contacts SET id = gen_random_uuid() WHERE id IS NULL")

    # =============================================
    # STEP 3: Add contact_id columns to referencing tables
    # =============================================
    contact_ref_tables = [
        "bookings",
        "conversations",
        "contact_strikes",
        "contact_suspensions",
        "customer_appointment_patterns",
        "reminders",
        "contact_consent",
        "contact_consent_history",
    ]
    for table in contact_ref_tables:
        op.add_column(table, sa.Column("contact_id", sa.UUID(), nullable=True))

    # Backfill contact_id from contact_phone join
    for table in contact_ref_tables:
        op.execute(f"""
            UPDATE {table} t
            SET contact_id = c.id
            FROM contacts c
            WHERE t.contact_phone = c.phone
        """)

    # =============================================
    # STEP 4: Drop old FK constraints on contact_phone
    # =============================================
    fk_mappings = {
        "bookings": "bookings_contact_phone_fkey",
        "conversations": "conversations_contact_phone_fkey",
        "contact_strikes": "contact_strikes_contact_phone_fkey",
        "contact_suspensions": "contact_suspensions_contact_phone_fkey",
        "customer_appointment_patterns": "customer_appointment_patterns_contact_phone_fkey",
        "reminders": "reminders_contact_phone_fkey",
        "contact_consent": "contact_consent_contact_phone_fkey",
        "contact_consent_history": "contact_consent_history_contact_phone_fkey",
    }
    for table, fk_name in fk_mappings.items():
        op.drop_constraint(fk_name, table, type_="foreignkey")

    # Drop unique constraint on contact_consent.contact_phone
    op.drop_constraint("contact_consent_contact_phone_key", "contact_consent", type_="unique")

    # Drop old unique constraint on pattern
    op.drop_constraint("uq_pattern_contact_type", "customer_appointment_patterns", type_="unique")

    # =============================================
    # STEP 5: Change contacts PK from phone to id
    # =============================================
    op.drop_constraint("contacts_pkey", "contacts", type_="primary")
    op.alter_column("contacts", "id", nullable=False)
    op.create_primary_key("contacts_pkey", "contacts", ["id"])

    # =============================================
    # STEP 6: Add new FK constraints (contact_id -> contacts.id)
    # =============================================
    for table in contact_ref_tables:
        op.alter_column(table, "contact_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_contact_id",
            table,
            "contacts",
            ["contact_id"],
            ["id"],
        )

    # Add tenant FK constraints for all tables including contacts
    for table in tables_needing_tenant_id + ["contacts"]:
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
        )

    # =============================================
    # STEP 7: SystemSetting PK change (key -> id)
    # =============================================
    op.add_column("system_settings", sa.Column("id", sa.UUID(), nullable=True, server_default=sa.text("gen_random_uuid()")))
    op.add_column("system_settings", sa.Column("tenant_id", sa.UUID(), nullable=True))

    op.execute("UPDATE system_settings SET id = gen_random_uuid() WHERE id IS NULL")

    op.drop_constraint("system_settings_pkey", "system_settings", type_="primary")
    op.alter_column("system_settings", "id", nullable=False)
    op.create_primary_key("system_settings_pkey", "system_settings", ["id"])
    op.create_index("ix_system_settings_tenant_id", "system_settings", ["tenant_id"])
    op.create_foreign_key(
        "fk_system_settings_tenant_id",
        "system_settings",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    # =============================================
    # STEP 8: Add new unique constraints
    # =============================================
    # Contact unique per tenant+phone
    op.create_unique_constraint("uq_contact_tenant_phone", "contacts", ["tenant_id", "phone"])
    # SystemSetting unique per tenant+key
    op.create_unique_constraint("uq_setting_tenant_key", "system_settings", ["tenant_id", "key"])
    # Pattern unique per tenant+contact+type
    op.create_unique_constraint(
        "uq_pattern_tenant_contact_type",
        "customer_appointment_patterns",
        ["tenant_id", "contact_id", "appointment_type_id"],
    )


def downgrade() -> None:
    # This migration is complex enough that downgrade should be done via backup restore
    raise NotImplementedError("Downgrade not supported — restore from backup")
