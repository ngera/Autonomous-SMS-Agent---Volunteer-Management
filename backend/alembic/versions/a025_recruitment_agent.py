"""Add recruitment agent tables.

Revision ID: a025_recruitment_agent
Revises: a024_drop_recurrence_weeks
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a025_recruitment_agent"
down_revision: Union[str, None] = "a024_drop_recurrence_weeks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE recruitment_campaign_status AS ENUM (
                'draft', 'awaiting_approval', 'active', 'paused',
                'completed', 'cancelled', 'failed'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE recruitment_wave_status AS ENUM (
                'planned', 'sending', 'sent', 'skipped', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE recruitment_report_channel AS ENUM ('sms', 'none');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recruitment_campaigns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            event_slot_id UUID NOT NULL REFERENCES specific_date_slots(id),
            status recruitment_campaign_status NOT NULL DEFAULT 'draft',
            goals JSONB NOT NULL,
            policy JSONB NOT NULL,
            plan_summary TEXT,
            plan_preview JSONB,
            message_templates JSONB,
            created_by_admin_id UUID NOT NULL REFERENCES admin_users(id),
            approved_by_admin_id UUID REFERENCES admin_users(id),
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_campaigns_tenant_id "
        "ON recruitment_campaigns(tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_campaigns_event_slot_id "
        "ON recruitment_campaigns(event_slot_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_campaigns_status "
        "ON recruitment_campaigns(status);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recruitment_waves (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            campaign_id UUID NOT NULL REFERENCES recruitment_campaigns(id) ON DELETE CASCADE,
            wave_number INTEGER NOT NULL,
            appointment_type_id UUID NOT NULL REFERENCES appointment_types(id),
            status recruitment_wave_status NOT NULL DEFAULT 'planned',
            scheduled_at TIMESTAMPTZ NOT NULL,
            targeted_contact_ids JSONB,
            selection_reason TEXT,
            announcement_id UUID REFERENCES announcements(id),
            sent_count INTEGER NOT NULL DEFAULT 0,
            signups_attributed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_waves_tenant_id "
        "ON recruitment_waves(tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_waves_campaign_id "
        "ON recruitment_waves(campaign_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_waves_status "
        "ON recruitment_waves(status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_waves_scheduled_at "
        "ON recruitment_waves(scheduled_at);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recruitment_signups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            campaign_id UUID NOT NULL REFERENCES recruitment_campaigns(id) ON DELETE CASCADE,
            wave_id UUID REFERENCES recruitment_waves(id) ON DELETE SET NULL,
            contact_id UUID NOT NULL REFERENCES contacts(id),
            appointment_type_id UUID NOT NULL REFERENCES appointment_types(id),
            booking_id UUID NOT NULL REFERENCES bookings(id),
            attributed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_signups_tenant_id "
        "ON recruitment_signups(tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_signups_campaign_id "
        "ON recruitment_signups(campaign_id);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recruitment_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            campaign_id UUID NOT NULL REFERENCES recruitment_campaigns(id) ON DELETE CASCADE,
            report_date DATE NOT NULL,
            payload JSONB NOT NULL,
            narrative TEXT,
            sent_via recruitment_report_channel NOT NULL DEFAULT 'none',
            delivered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_reports_tenant_id "
        "ON recruitment_reports(tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_reports_campaign_id "
        "ON recruitment_reports(campaign_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_recruitment_reports_report_date "
        "ON recruitment_reports(report_date);"
    )

    op.execute(
        "ALTER TABLE announcements ADD COLUMN IF NOT EXISTS "
        "recruitment_wave_id UUID REFERENCES recruitment_waves(id);"
    )

    # Allow contact_id NULL on conversations so admin-SMS (sender_type='admin')
    # conversations can be created. The Conversation model already targets
    # this — see a006_admin_phone_and_sender_type — but the column was left
    # NOT NULL from a002, which silently breaks admin-conversation INSERTs
    # (pipeline.py passes contact_id=None for admin). Recruitment-report
    # mirroring (locked decision #2) also depends on this.
    op.execute(
        "ALTER TABLE conversations ALTER COLUMN contact_id DROP NOT NULL;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE conversations ALTER COLUMN contact_id SET NOT NULL;"
    )
    op.execute("ALTER TABLE announcements DROP COLUMN IF EXISTS recruitment_wave_id;")
    op.execute("DROP TABLE IF EXISTS recruitment_reports;")
    op.execute("DROP TABLE IF EXISTS recruitment_signups;")
    op.execute("DROP TABLE IF EXISTS recruitment_waves;")
    op.execute("DROP TABLE IF EXISTS recruitment_campaigns;")
    op.execute("DROP TYPE IF EXISTS recruitment_report_channel;")
    op.execute("DROP TYPE IF EXISTS recruitment_wave_status;")
    op.execute("DROP TYPE IF EXISTS recruitment_campaign_status;")
