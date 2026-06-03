"""Per-tenant snooze + dismiss state for Needs-You-Now alerts.

One row per (tenant, alert_id). Re-snoozing or re-dismissing the same
alert upserts via ON CONFLICT — the most recent action wins.

State is stored as a plain string with a CHECK constraint so we can add
new states (e.g. 'archived', 'forwarded') without an enum migration.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


ALERT_STATE_SNOOZED = "snoozed"
ALERT_STATE_DISMISSED = "dismissed"


class DashboardAlertState(Base):
    __tablename__ = "dashboard_alert_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    alert_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismiss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
