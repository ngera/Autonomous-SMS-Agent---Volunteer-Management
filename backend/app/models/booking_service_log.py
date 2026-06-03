"""Phase 3 — actual services performed during a booking.

One booking represents *attendance* at one event slot. The actual
*services* the volunteer performed (or requested to perform) live in
booking_service_log. This lets:

  - SWITCH/ALSO requests (volunteer texts mid-event) be captured as
    pending entries that need admin approval before they "count."
  - Post-event review aggregate per-service hours by reading these
    rows (Phase 4).
  - Multi-service per-booking analytics (Phase 5 milestones tracking
    specific services).

Status lifecycle:
  pending → approved   (admin clicks Approve OR texts APPROVE <name>)
  pending → rejected   (admin clicks Reject OR texts REJECT <name>)
  pending → superseded (a newer pending row from the same booking
                        replaces this one; decision #17)

Source values: 'planned' (initial mirror of Booking.appointment_type),
'volunteer_sms' (SWITCH/ALSO intent), 'admin' (admin UI created).

Optimistic concurrency: every status change must include the
expected version in its WHERE clause and bump version+1 (decision #29b).
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Source values (CHECK enforced at DB).
BSL_SOURCE_PLANNED = "planned"
BSL_SOURCE_VOLUNTEER_SMS = "volunteer_sms"
BSL_SOURCE_ADMIN = "admin"

# Status values (CHECK enforced at DB).
BSL_STATUS_PENDING = "pending"
BSL_STATUS_APPROVED = "approved"
BSL_STATUS_REJECTED = "rejected"
BSL_STATUS_SUPERSEDED = "superseded"


class BookingServiceLog(Base):
    __tablename__ = "booking_service_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_bsl_status",
        ),
        CheckConstraint(
            "source IN ('planned', 'volunteer_sms', 'admin')",
            name="ck_bsl_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointment_types.id"), nullable=False
    )
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # null = still in progress
    ended_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BSL_STATUS_PENDING,
        server_default=BSL_STATUS_PENDING,
    )
    # Optimistic concurrency. Bump by 1 on every status change.
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    approved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
