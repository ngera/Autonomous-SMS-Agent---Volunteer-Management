import enum
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PatternConfidence(str, enum.Enum):
    DEFAULT = "default"
    EMERGING = "emerging"
    PERSONAL = "personal"


class CustomerAppointmentPattern(Base):
    __tablename__ = "customer_appointment_patterns"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contact_id",
            "appointment_type_id",
            name="uq_pattern_tenant_contact_type",
        ),
    )

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
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointment_types.id"), nullable=False
    )
    completed_booking_count: Mapped[int] = mapped_column(Integer, default=0)
    calculated_interval_days: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    blended_interval_days: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    admin_default_days: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    confidence: Mapped[PatternConfidence] = mapped_column(
        Enum(PatternConfidence, name="pattern_confidence"),
        default=PatternConfidence.DEFAULT,
    )
    outliers_removed: Mapped[int] = mapped_column(Integer, default=0)
    manual_override_days: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    last_calculated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_due_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
