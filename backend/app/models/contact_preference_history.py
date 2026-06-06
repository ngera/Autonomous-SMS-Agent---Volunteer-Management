"""Append-only history of changes to a contact's stored preferences.

Used today to track explicit changes to roster_visibility (e.g. a
volunteer messaging "show my first name" or "hide me"). Shaped so
future single-value preferences can land here under a different
``field`` discriminator without a new table.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Field discriminator values currently in use.
PREFERENCE_FIELD_ROSTER_VISIBILITY = "roster_visibility"

# Source values currently in use.
PREFERENCE_SOURCE_USER_SMS = "user_sms"
PREFERENCE_SOURCE_ADMIN = "admin"


class ContactPreferenceHistory(Base):
    __tablename__ = "contact_preference_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_value: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=PREFERENCE_SOURCE_USER_SMS
    )
    source_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
