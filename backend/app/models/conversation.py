import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    message_history: Mapped[dict] = mapped_column(JSONB, default=list)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status"), nullable=False
    )
    consent_verified_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_message_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sender_type: Mapped[str] = mapped_column(
        String(10), default="customer", server_default="customer"
    )
