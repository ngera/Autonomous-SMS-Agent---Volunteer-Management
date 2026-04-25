import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.tenant import ContactPreference


class TenantCreate(BaseModel):
    name: str
    slug: str
    business_name: str
    business_domain: str = ""
    business_timezone: str = "America/New_York"
    admin_panel_url: str = ""
    api_domain: str = ""
    # Admin login credentials (used to create owner user on tenant creation)
    admin_email: str | None = None
    admin_password: str | None = None
    # Store info
    phone: str | None = None
    email: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    address_country: str | None = None
    # Billing
    billing_email: str | None = None
    billing_address_street: str | None = None
    billing_address_city: str | None = None
    billing_address_state: str | None = None
    billing_address_zip: str | None = None
    billing_address_country: str | None = None
    # Primary contact
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_preference: ContactPreference | None = None
    # Credentials
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
    # Store info
    phone: str | None = None
    email: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    address_country: str | None = None
    # Billing
    billing_email: str | None = None
    billing_address_street: str | None = None
    billing_address_city: str | None = None
    billing_address_state: str | None = None
    billing_address_zip: str | None = None
    billing_address_country: str | None = None
    # Primary contact
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_preference: ContactPreference | None = None
    # Pause
    is_paused: bool | None = None
    # Credentials
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
    # Store info
    phone: str | None = None
    email: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    # Contact summary
    contact_name: str | None = None
    contact_email: str | None = None
    # Pause / deactivate
    is_paused: bool = False
    paused_at: datetime | None = None
    deactivated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantDetailResponse(TenantResponse):
    """Full response including all profile fields and credential presence flags."""
    # Full address
    address_street: str | None = None
    address_zip: str | None = None
    address_country: str | None = None
    # Billing
    billing_email: str | None = None
    billing_address_street: str | None = None
    billing_address_city: str | None = None
    billing_address_state: str | None = None
    billing_address_zip: str | None = None
    billing_address_country: str | None = None
    # Contact
    contact_phone: str | None = None
    contact_preference: ContactPreference | None = None
    # Credential presence flags
    has_twilio: bool = False
    has_anthropic: bool = False
    has_google_calendar: bool = False
    has_resend: bool = False
    # Masked credential values (for display only)
    twilio_account_sid_masked: str | None = None
    twilio_auth_token_masked: str | None = None
    anthropic_api_key_masked: str | None = None
    google_client_id_masked: str | None = None
    google_client_secret_masked: str | None = None
    google_refresh_token_masked: str | None = None
    resend_api_key_masked: str | None = None
    resend_from_email: str | None = None


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    total: int


class TenantSummaryItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_paused: bool
    customers: int = 0
    bookings: int = 0
    conversations: int = 0
    reminders: int = 0
    revenue: float = 0.0


class SuperAdminDashboardSummary(BaseModel):
    total_tenants: int
    active_tenants: int
    paused_tenants: int
    total_customers: int
    total_bookings: int
    total_conversations: int
    total_reminders: int
    total_revenue: float
    tenants: list[TenantSummaryItem]
