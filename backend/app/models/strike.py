import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrikeClassification(str, enum.Enum):
    IRRELEVANT = "irrelevant"
    ABUSIVE = "abusive"
    INJECTION = "injection"


class ScreenerMethod(str, enum.Enum):
    RULE_BASED = "rule_based"
    AI_MICRO_PROMPT = "ai_micro_prompt"


class ContactStrike(Base):
    __tablename__ = "contact_strikes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    strike_number: Mapped[int] = mapped_column(Integer, nullable=False)
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[StrikeClassification] = mapped_column(
        Enum(StrikeClassification, name="strike_classification"), nullable=False
    )
    screener_method: Mapped[ScreenerMethod] = mapped_column(
        Enum(ScreenerMethod, name="screener_method"), nullable=False
    )
    screener_response: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decayed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
