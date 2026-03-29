from fastapi import APIRouter, HTTPException, Request, status

from app.core.dependencies import CurrentUser, DbSession
from app.middleware.ratelimit import AUTH_RATE_LIMIT, limiter
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth import (
    authenticate_user,
    logout_user,
    refresh_access_token,
    request_password_reset,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, body: LoginRequest, db: DbSession):
    """Authenticate admin user and return JWT tokens."""
    try:
        tokens = await authenticate_user(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return tokens


@router.get("/me")
async def get_me(current_user: CurrentUser, db: DbSession):
    """Return the current authenticated admin user's profile."""
    result = {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "tenant_id": str(current_user.tenant_id) if current_user.tenant_id else None,
        "tenant_name": None,
    }
    if current_user.tenant_id:
        from app.models.tenant import Tenant
        from sqlalchemy import select

        tenant_result = await db.execute(
            select(Tenant.name).where(Tenant.id == current_user.tenant_id)
        )
        result["tenant_name"] = tenant_result.scalar_one_or_none()
    return result


@router.post("/logout", response_model=MessageResponse)
async def logout(db: DbSession, current_user: CurrentUser):
    """Invalidate the current admin session."""
    await logout_user(db, current_user)
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh(request: Request, body: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    try:
        tokens = await refresh_access_token(body.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return tokens


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def reset_password(request: Request, body: PasswordResetRequest):
    """Trigger a password reset email.

    Always returns success to prevent email enumeration.
    """
    await request_password_reset(body.email)
    return {"message": "If an account exists with that email, a reset link has been sent"}
