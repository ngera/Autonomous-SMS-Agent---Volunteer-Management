import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactPreference(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"


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

    # Store contact info
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Billing info
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address_street: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_address_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_address_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Primary contact person
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_preference: Mapped[ContactPreference | None] = mapped_column(
        Enum(ContactPreference, name="contact_preference", values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )

    # Pause / deactivate
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    paused_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
