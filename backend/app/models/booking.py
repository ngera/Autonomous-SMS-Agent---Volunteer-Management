import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class RosterVisibility(str, enum.Enum):
    HIDDEN = "hidden"
    FIRST_NAME = "first_name"
    FULL_NAME = "full_name"


class Booking(Base):
    __tablename__ = "bookings"

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
    # Explicit link to the event the signup belongs to. NULL for
    # regular-availability bookings (no specific-date slot). When a slot's
    # date or time changes, this lets the cascade find affected bookings
    # by FK instead of by date-match — see a028 migration.
    event_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specific_date_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Set when the slot's date/time changes. Volunteer is asked to
    # confirm-or-opt-out by SMS; the customer LLM preamble surfaces
    # this so a YES reply confirms and STOP cancels.
    pending_reconfirmation_until: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), nullable=False
    )
    roster_visibility: Mapped[RosterVisibility] = mapped_column(
        String(20),
        default=RosterVisibility.FIRST_NAME.value,
        server_default=RosterVisibility.FIRST_NAME.value,
        nullable=False,
    )
    price_at_booking: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    calendar_event_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    ics_sequence: Mapped[int] = mapped_column(Integer, default=0)
    ics_new_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ics_update_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
