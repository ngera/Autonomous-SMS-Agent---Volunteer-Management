"""Phase 4 — locked post-event review per booking.

Lifecycle:
  pending   ─(admin approves)──▶ approved
  pending   ─(admin skips)─────▶ skipped
  no_show   ─(admin flips)─────▶ pending
  approved  ─(OWNER/SUPER_ADMIN unlocks)─▶ pending (within 24h for OWNER)

Status meanings:
  - pending:   needs admin attention; grade not yet assigned
  - approved:  admin reviewed + assigned grade; immutable except via unlock
  - no_show:   auto-created at T+start+30min; volunteer never checked in
  - skipped:   admin closed without grading (decision #26 — "nothing to grade
               but the volunteer did show up")

Hours derivation (decision #10): reconstructed at approval from
agent_call_log volunteer_check_in / volunteer_check_out events; stored
into `segments` JSONB; `total_hours` snapshotted from
compute_total_hours(segments, slot.start_at, tenant_settings).

Unlock tracking (decision #16 + R2): unlock_count increments atomically
alongside the unlock metadata. Full chronological history is in
agent_call_log under EVENT_REVIEW_UNLOCKED.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Status values (CHECK constraint at DB).
REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_NO_SHOW = "no_show"
REVIEW_STATUS_SKIPPED = "skipped"


class BookingReview(Base):
    __tablename__ = "booking_review"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'no_show', 'skipped')",
            name="ck_review_status",
        ),
        CheckConstraint(
            "grade IS NULL OR (grade BETWEEN 1 AND 5)",
            name="ck_review_grade",
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
    # UNIQUE constraint declared at the DB enforces one review per booking.
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=REVIEW_STATUS_PENDING,
        server_default=REVIEW_STATUS_PENDING,
    )
    grade: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    grade_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshot at approval (decision #10).
    total_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Multi-segment list of {in, out, source_in, source_out} dicts.
    segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    final_check_in_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    final_check_out_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    reviewed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Unlock tracking (most recent only; full history in agent_call_log).
    unlocked_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unlocked_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    unlock_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
