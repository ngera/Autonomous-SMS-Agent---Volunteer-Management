from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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
    business_timezone: str = "Europe/London"
    environment: str = "development"
    secret_key: str = "change-me-in-production"


settings = Settings()
