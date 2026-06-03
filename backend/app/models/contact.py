import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContactSex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class ContactStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_contact_tenant_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sex: Mapped[ContactSex | None] = mapped_column(
        Enum(ContactSex, name="contact_sex", values_callable=lambda e: [x.value for x in e]), nullable=True
    )
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus, name="contact_status"), default=ContactStatus.ACTIVE
    )
    all_services_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    background_check_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    availability: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    weekly_hours: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    unavailable_dates: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    reminder_preference_days: Mapped[int] = mapped_column(Integer, default=7)
    # Per-contact default for how their name shows on the volunteer roster.
    # Mirrors the values of app.models.booking.RosterVisibility (stored as a
    # short string so we don't need a Postgres enum migration to add this).
    # NULL means "not yet chosen" — book_appointment falls back to first_name
    # in that case AND asks the volunteer for their preference. Once set, the
    # answer carries forward to all future bookings so they aren't re-asked.
    default_roster_visibility: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    # Admin auto-link (decision #22). When an admin_users row is created
    # we upsert a Contact and link via this FK. The unique partial index
    # `ux_contacts_admin_user_id` enforces at-most-one Contact per admin.
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Recruiter wave opt-out (decision #30). Defaults FALSE for ordinary
    # volunteers; TRUE for admin-linked Contacts so admins don't silently
    # start receiving recruitment invites the moment they're added.
    exclude_from_recruiting: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    # Phase 4 — historical quality cache (decision #24).
    # Decay-weighted average grade over last N approved reviews;
    # used as a soft weight in the recruiter targeting layer.
    # Cold-start (None or approved_reviews_count == 0) → neutral weight.
    historical_quality_score: Mapped[float | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    historical_quality_updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_reviews_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    consent = relationship("ContactConsent", back_populates="contact", uselist=False)
