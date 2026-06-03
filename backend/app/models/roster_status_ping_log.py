"""Observability table for Phase 2 roster status pings.

One row per (slot, admin, scheduled_for, channel). Powers:
  - Idempotency: at tick time, skip if a row already exists.
  - STOP STATUS / STOP STATUS ALL: pre-insert with skipped_reason.
  - Suppression rule: pre-insert remaining T+* rows with
    skipped_reason='event_full_checked_in' when everyone is checked in.
  - Observability: queryable per tenant for dispatch / silence metrics.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


PING_CHANNEL_SMS = "sms"
PING_CHANNEL_EMAIL = "email"
PING_CHANNEL_IN_APP = "in_app"

PING_SKIPPED_ADMIN_SILENCED = "admin_silenced"
PING_SKIPPED_EVENT_FULL = "event_full_checked_in"
PING_SKIPPED_DISPATCH_FAILED = "dispatch_failed"
PING_SKIPPED_DUPLICATE = "duplicate"


class RosterStatusPingLog(Base):
    __tablename__ = "roster_status_ping_log"
    __table_args__ = (
        UniqueConstraint(
            "slot_id", "admin_user_id", "scheduled_for", "channel",
            name="uq_ping_per_recipient_per_time",
        ),
        CheckConstraint(
            "channel IN ('sms', 'email', 'in_app')",
            name="ck_ping_channel",
        ),
        CheckConstraint(
            "skipped_reason IS NULL OR skipped_reason IN ("
            "'admin_silenced','event_full_checked_in',"
            "'dispatch_failed','duplicate')",
            name="ck_ping_skipped_reason",
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
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specific_date_slots.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=False,
    )
    scheduled_for: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    skipped_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
