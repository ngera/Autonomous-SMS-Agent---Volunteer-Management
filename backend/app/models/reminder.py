import enum
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    BOOKED = "booked"
    SKIPPED = "skipped"
    NO_RESPONSE = "no_response"
    CANCELLED = "cancelled"


class Reminder(Base):
    __tablename__ = "reminders"

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
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointment_types.id"), nullable=False
    )
    pattern_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scheduled_for: Mapped[Date] = mapped_column(Date, nullable=False)
    sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    follow_up_sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status"), nullable=False
    )
    converted_to_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True
    )
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
