import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AvailabilityRule(Base):
    """Recurring weekly schedule window.

    service_config: list of services needed during this window, each with:
      [{"appointment_type_id": "<uuid>", "min_required": 3, "max_allowed": 6}, ...]

    When NULL/empty, all active appointment types are allowed with min=1, max=1.
    """
    __tablename__ = "availability_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon..6=Sun
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0)
    service_config: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_roster_sharing: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class SpecificDateSlot(Base):
    """One-off event or special availability on a specific date.

    service_config follows the same format as AvailabilityRule.
    """
    __tablename__ = "specific_date_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0)
    service_config: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_roster_sharing: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    # Free-form description used by the AI when a volunteer asks about
    # the event. Surfaced via check_availability and the new
    # get_event_info tool so the assistant can answer "what's this
    # event about?" without an admin in the loop.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance: when an admin clicks "Start Campaign" on a recurring
    # event instance, the system materializes that occurrence into a
    # specific_date_slot so a campaign can attach. This FK records the
    # source rule. ON DELETE SET NULL: deleting the rule strands the
    # slot as a standalone specific event but preserves bookings.
    availability_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Set by the propagation engine when the parent rule changed but
    # this slot couldn't safely auto-absorb the new values (had
    # bookings or an active campaign). The dashboard surfaces these
    # as "Rule changed — review" alerts and an admin chooses to
    # accept (apply the diff) or ignore (clear the flag).
    rule_drift_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # JSONB list of {"field", "from", "to"} entries — the human-readable
    # diff the alert/review modal renders.
    rule_drift_summary: Mapped[list | None] = mapped_column(JSONB, nullable=True)
