import uuid

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Business config
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_domain: Mapped[str] = mapped_column(String(255), default="")
    business_timezone: Mapped[str] = mapped_column(
        String(100), default="America/New_York"
    )
    admin_panel_url: Mapped[str] = mapped_column(String(500), default="")
    api_domain: Mapped[str] = mapped_column(String(255), default="")

    # Per-tenant external credentials
    twilio_account_sid: Mapped[str | None] = mapped_column(Text, nullable=True)
    twilio_auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    twilio_phone_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True
    )
    anthropic_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    resend_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    resend_from_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
