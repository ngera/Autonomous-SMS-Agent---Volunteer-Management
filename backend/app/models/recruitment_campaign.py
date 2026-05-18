import enum
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WaveStatus(str, enum.Enum):
    PLANNED = "planned"
    SENDING = "sending"
    SENT = "sent"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ReportChannel(str, enum.Enum):
    SMS = "sms"
    NONE = "none"


class RecruitmentCampaign(Base):
    __tablename__ = "recruitment_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    event_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specific_date_slots.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(
            CampaignStatus,
            name="recruitment_campaign_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=CampaignStatus.DRAFT,
        nullable=False,
        index=True,
    )
    goals: Mapped[list] = mapped_column(JSONB, nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plan_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_preview: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message_templates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False
    )
    approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    approved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RecruitmentWave(Base):
    __tablename__ = "recruitment_waves"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wave_number: Mapped[int] = mapped_column(Integer, nullable=False)
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointment_types.id"), nullable=False
    )
    status: Mapped[WaveStatus] = mapped_column(
        Enum(
            WaveStatus,
            name="recruitment_wave_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=WaveStatus.PLANNED,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    targeted_contact_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    announcement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("announcements.id"), nullable=True
    )
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signups_attributed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecruitmentSignup(Base):
    __tablename__ = "recruitment_signups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wave_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_waves.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointment_types.id"), nullable=False
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False
    )
    attributed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecruitmentReport(Base):
    __tablename__ = "recruitment_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_via: Mapped[ReportChannel] = mapped_column(
        Enum(
            ReportChannel,
            name="recruitment_report_channel",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=ReportChannel.NONE,
        nullable=False,
    )
    delivered_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
