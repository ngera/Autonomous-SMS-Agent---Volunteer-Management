"""Phase 5 — award template (milestone / badge / award).

`kind` is the discriminator (decision #7 — kind lives here, NOT on
volunteer_recognition). It drives:
  - UI rendering (milestone = progress, badge = chip, award = ribbon)
  - Validation at save (milestone requires auto_criteria; award typically forbids)
  - Default uniqueness_scope (lifetime for milestones+badges, per_period for
    Volunteer of the Month-style awards)

`uniqueness_scope` is per-definition (decision #27):
  - lifetime: one (contact, definition) ever
  - per_event: one (contact, definition, slot) — "MVP of <Event>"
  - per_period: one (contact, definition, period_key) — "Volunteer of the Month"

`auto_criteria` is JSONB; when present, the recognition engine evaluates it
after every booking_review approval. Supported metrics:
  {"metric": "hours", "threshold": 10}
  {"metric": "events_completed", "threshold": 50}
  {"metric": "service_count", "service_id": "<uuid>", "threshold": 5}
  {"metric": "avg_grade_over_last_n", "n": 10, "threshold": 4.5}
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Kind values (CHECK constraint at DB).
AWARD_KIND_MILESTONE = "milestone"
AWARD_KIND_BADGE = "badge"
AWARD_KIND_AWARD = "award"

# Uniqueness scope values.
AWARD_SCOPE_LIFETIME = "lifetime"
AWARD_SCOPE_PER_EVENT = "per_event"
AWARD_SCOPE_PER_PERIOD = "per_period"

# Period unit values (only meaningful when scope=per_period).
PERIOD_UNIT_MONTH = "month"
PERIOD_UNIT_QUARTER = "quarter"
PERIOD_UNIT_YEAR = "year"


class AwardDefinition(Base):
    __tablename__ = "award_definition"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_award_definition_tenant_key"),
        CheckConstraint(
            "kind IN ('milestone', 'badge', 'award')",
            name="ck_award_definition_kind",
        ),
        CheckConstraint(
            "uniqueness_scope IN ('lifetime', 'per_event', 'per_period')",
            name="ck_award_definition_uniqueness_scope",
        ),
        CheckConstraint(
            "(uniqueness_scope = 'per_period' AND period_unit IS NOT NULL) "
            "OR (uniqueness_scope != 'per_period' AND period_unit IS NULL)",
            name="ck_award_definition_period_unit",
        ),
        CheckConstraint(
            "period_unit IS NULL OR period_unit IN ('month', 'quarter', 'year')",
            name="ck_award_definition_period_unit_value",
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
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Stable string id per tenant (e.g. '10_hour_milestone'); used in
    # URLs + analytics. Tenant-unique via UniqueConstraint above.
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Null = manual-only (admin grants from the recognition admin UI).
    auto_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    uniqueness_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AWARD_SCOPE_LIFETIME,
        server_default=AWARD_SCOPE_LIFETIME,
    )
    # Only meaningful when uniqueness_scope == per_period.
    period_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
