import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    slug: str
    business_name: str
    business_domain: str = ""
    business_timezone: str = "America/New_York"
    admin_panel_url: str = ""
    api_domain: str = ""
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    anthropic_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None
    resend_api_key: str | None = None
    resend_from_email: str | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    is_active: bool | None = None
    business_name: str | None = None
    business_domain: str | None = None
    business_timezone: str | None = None
    admin_panel_url: str | None = None
    api_domain: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    anthropic_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None
    resend_api_key: str | None = None
    resend_from_email: str | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    business_name: str
    business_domain: str
    business_timezone: str
    admin_panel_url: str
    api_domain: str
    twilio_phone_number: str | None
    created_at: datetime
    updated_at: datetime
    # Credentials are NOT exposed in responses for security

    model_config = {"from_attributes": True}


class TenantDetailResponse(TenantResponse):
    """Full response including credential presence flags (not values)."""

    has_twilio: bool = False
    has_anthropic: bool = False
    has_google_calendar: bool = False
    has_resend: bool = False


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    total: int
