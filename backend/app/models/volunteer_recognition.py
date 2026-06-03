"""Phase 5 — earned milestone / badge / award.

`kind` is NOT stored here (decision #7); it's derivable via the FK
to award_definition.

Uniqueness is enforced via three partial unique indexes declared in
the migration (a041). The recognition engine populates the appropriate
columns based on the definition's uniqueness_scope:

  - lifetime : both earned_via_slot_id AND period_key are NULL
  - per_event: earned_via_slot_id is set, period_key is NULL
  - per_period: period_key is set, earned_via_slot_id is NULL

period_key derivation (when scope=per_period):
  - month   → 'YYYY-MM'
  - quarter → 'YYYY-Qn'   (n = 1..4)
  - year    → 'YYYY'

`granted_by_admin_id` is set for manual grants (admin clicked Grant in
the recognition admin UI); NULL for auto-grants from the engine.
"""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VolunteerRecognition(Base):
    __tablename__ = "volunteer_recognition"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("award_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    earned_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set when an auto-grant happens via review approval.
    earned_via_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking_review.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Set when uniqueness_scope='per_event'.
    earned_via_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specific_date_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Set when uniqueness_scope='per_period'. Derived from earned_at +
    # definition.period_unit (e.g. '2026-06' for monthly).
    period_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Set for manual admin grants; NULL for auto.
    granted_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
