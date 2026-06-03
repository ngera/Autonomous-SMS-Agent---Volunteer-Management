"""Walk-up candidate records — unknown phones that texted in.

Row 4/5 of the inbound SMS routing matrix: when an unknown phone
texts the system, we capture them here instead of creating an
anonymous UNCONTACTED Contact stub (which would pollute the volunteer
roster). Admins act on these via the /candidates UI:
  - Invite → promotes to a real Contact via existing recruiter invite flow
  - Dismiss → marks as terminal-dead; preserved for audit (1-year cap)

last_notified_at powers the 24h notification rate limit (decision #28
mechanics) so a stranger texting repeatedly can't spam admins.

See event_lifecycle_plan.md Row 4 section + decisions #29(c), #32.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Status values. Plain strings for ergonomics; CHECK constraint at the DB.
CANDIDATE_STATUS_NEW = "new"
CANDIDATE_STATUS_INVITED = "invited"
CANDIDATE_STATUS_DISMISSED = "dismissed"


class VolunteerCandidate(Base):
    __tablename__ = "volunteer_candidate"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_candidate_tenant_phone"),
        CheckConstraint(
            "status IN ('new', 'invited', 'dismissed')",
            name="ck_candidate_status",
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
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    first_seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Powers 24h notification rate-limit. Updated when notification fires.
    last_notified_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Which event triggered the most recent signal (Row 4 picker hierarchy).
    last_signal_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specific_date_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Status — 'new' (default), 'invited' (admin clicked Invite), 'dismissed'.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CANDIDATE_STATUS_NEW,
        server_default=CANDIDATE_STATUS_NEW,
    )
    invited_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    dismissed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    # Set on Invite completion. Links candidate to the real Contact.
    # ON DELETE SET NULL — deleting the Contact doesn't delete the audit row.
    promoted_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
