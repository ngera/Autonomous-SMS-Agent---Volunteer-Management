from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.admin_user import AdminUser

logger = get_logger("auth")

SUPABASE_AUTH_URL = f"{settings.supabase_service_key and 'https://' + settings.database_url.split('@')[1].split(':')[0].replace('db.', '') + '.supabase.co' if settings.supabase_service_key else 'http://localhost:54321'}"

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> dict:
    """Authenticate admin user via Supabase Auth.

    Returns token dict on success. Raises ValueError on failure.
    """
    # Check if user exists and is not locked
    result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    user = result.scalar_one_or_none()

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        raise ValueError(
            f"Account locked. Try again in {remaining + 1} minutes."
        )

    # Authenticate via Supabase Auth
    async with httpx.AsyncClient() as client:
        # Use Supabase GoTrue API for authentication
        supabase_url = _get_supabase_url()
        response = await client.post(
            f"{supabase_url}/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers={
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
            },
        )

    if response.status_code != 200:
        # Increment failed login count
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                logger.warning("Account locked for user %s after %d failed attempts", email, user.failed_login_count)
            await db.flush()

        # Generic error message to prevent enumeration
        raise ValueError("Invalid email or password")

    data = response.json()

    # Reset failed login count and update last login
    if user:
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_type": "bearer",
        "expires_in": data.get("expires_in", 1800),
    }


async def refresh_access_token(refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token via Supabase Auth."""
    async with httpx.AsyncClient() as client:
        supabase_url = _get_supabase_url()
        response = await client.post(
            f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
            headers={
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
            },
        )

    if response.status_code != 200:
        raise ValueError("Invalid or expired refresh token")

    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_type": "bearer",
        "expires_in": data.get("expires_in", 1800),
    }


async def request_password_reset(email: str) -> None:
    """Trigger password reset email via Supabase Auth."""
    async with httpx.AsyncClient() as client:
        supabase_url = _get_supabase_url()
        await client.post(
            f"{supabase_url}/auth/v1/recover",
            json={"email": email},
            headers={
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
            },
        )
    # Always return success to prevent email enumeration


async def logout_user(db: AsyncSession, user: AdminUser) -> None:
    """Handle server-side logout. Supabase handles token invalidation client-side."""
    logger.info("Admin user %s logged out", user.email)


def _get_supabase_url() -> str:
    """Get Supabase project URL from settings or extract from DATABASE_URL."""
    # Prefer explicit SUPABASE_URL setting
    if settings.supabase_url:
        return settings.supabase_url

    # Fallback: extract from DATABASE_URL format: postgresql+asyncpg://user:pass@db.xyz.supabase.co:5432/postgres
    try:
        host = settings.database_url.split("@")[1].split(":")[0]
        project_ref = host.replace("db.", "").replace(".supabase.co", "")
        return f"https://{project_ref}.supabase.co"
    except (IndexError, AttributeError):
        return "http://localhost:54321"
