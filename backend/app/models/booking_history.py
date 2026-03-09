import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.booking import BookingStatus


class BookingEventType(str, enum.Enum):
    CREATED = "created"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    STATUS_CHANGED = "status_changed"


class ChangedBy(str, enum.Enum):
    USER_SMS = "user_sms"
    ADMIN = "admin"
    SCHEDULER = "scheduler"


class BookingHistory(Base):
    __tablename__ = "booking_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False
    )
    event_type: Mapped[BookingEventType] = mapped_column(
        Enum(BookingEventType, name="booking_event_type"), nullable=False
    )
    previous_scheduled_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    new_scheduled_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    previous_status: Mapped[BookingStatus | None] = mapped_column(
        Enum(BookingStatus, name="booking_status", create_type=False), nullable=True
    )
    new_status: Mapped[BookingStatus | None] = mapped_column(
        Enum(BookingStatus, name="booking_status", create_type=False), nullable=True
    )
    changed_by: Mapped[ChangedBy] = mapped_column(
        Enum(ChangedBy, name="changed_by"), nullable=False
    )
    changed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
