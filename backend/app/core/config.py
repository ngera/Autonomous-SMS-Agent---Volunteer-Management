from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent
# Monorepo root .env, then backend/.env — later files override when both exist
_ENV_FILES: tuple[str, ...] = tuple(
    str(p.resolve())
    for p in (_REPO_ROOT / ".env", _BACKEND_ROOT / ".env")
    if p.is_file()
) or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str
    supabase_url: str = ""  # e.g., https://xyz.supabase.co
    supabase_jwt_secret: str
    supabase_service_key: str = ""

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    # When true, services/sms.py::send_sms short-circuits and returns a fake
    # SID without calling Twilio. Used while the Twilio Subaccounts plan
    # (memory/twilio_subaccounts_plan.md) is pending so the Multi-Volunteer
    # Test workflow can run without valid per-tenant Twilio credentials.
    sms_suppress: bool = False

    # Anthropic
    anthropic_api_key: str

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # Resend
    resend_api_key: str = ""
    resend_from_email: str = "notifications@yourbusiness.com"

    # Application
    admin_panel_url: str = "http://localhost:5173"
    api_domain: str = "localhost:8000"
    business_name: str = "Your Business"
    business_domain: str = "yourbusiness.com"
    business_timezone: str = "America/New_York"
    environment: str = "development"
    secret_key: str = "change-me-in-production"


settings = Settings()
