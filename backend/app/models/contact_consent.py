import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ConsentStatus(str, enum.Enum):
    UNCONTACTED = "uncontacted"
    PENDING = "pending"
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"
    BLOCKED = "blocked"


class OptInMethod(str, enum.Enum):
    SMS_REPLY = "sms_reply"
    ADMIN_MANUAL = "admin_manual"
    IMPORTED = "imported"
    # Decision #22: auto-OPTED_IN when an admin_users row gets a linked
    # Contact (either at admin creation or via the backfill in a034).
    ADMIN_AUTOLINK = "admin_autolink"


class OptOutMethod(str, enum.Enum):
    SMS_STOP = "sms_stop"
    SMS_REPLY = "sms_reply"
    ADMIN_MANUAL = "admin_manual"


class ContactConsent(Base):
    __tablename__ = "contact_consent"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status"), nullable=False
    )
    opted_in_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opted_out_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opt_in_method: Mapped[OptInMethod | None] = mapped_column(
        Enum(
            OptInMethod,
            name="opt_in_method",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    opt_out_method: Mapped[OptOutMethod | None] = mapped_column(
        Enum(OptOutMethod, name="opt_out_method"), nullable=True
    )
    last_status_change_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    contact = relationship("Contact", back_populates="consent")


class ContactConsentHistory(Base):
    __tablename__ = "contact_consent_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", create_type=False), nullable=False
    )
    new_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", create_type=False), nullable=False
    )
    changed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    changed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
