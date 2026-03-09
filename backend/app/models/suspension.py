import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuspensionType(str, enum.Enum):
    AUTO_STRIKE = "auto_strike"
    AUTO_ABUSIVE = "auto_abusive"
    MANUAL = "manual"


class ReviewDecision(str, enum.Enum):
    LIFTED = "lifted"
    CONFIRMED = "confirmed"
    BANNED = "banned"


class ContactSuspension(Base):
    __tablename__ = "contact_suspensions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_phone: Mapped[str] = mapped_column(
        String(20), ForeignKey("contacts.phone"), nullable=False
    )
    suspended_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    suspension_type: Mapped[SuspensionType] = mapped_column(
        Enum(SuspensionType, name="suspension_type"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    strike_ids: Mapped[list | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    notification_sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    reviewed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_decision: Mapped[ReviewDecision | None] = mapped_column(
        Enum(ReviewDecision, name="review_decision"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
