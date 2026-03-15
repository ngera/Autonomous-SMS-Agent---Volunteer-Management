from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser

logger = get_logger("deps")
security = HTTPBearer()

# Cached JWKS keys (fetched once from Supabase)
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch and cache JWKS from Supabase for ES256 token verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    if not settings.supabase_url:
        return {}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
                headers={"apikey": settings.supabase_service_key},
                timeout=10,
            )
            if resp.status_code == 200:
                _jwks_cache = resp.json()
                return _jwks_cache
    except Exception as e:
        logger.warning("Failed to fetch JWKS: %s", e)

    return {}


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    """Validate JWT and return the authenticated admin user."""
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "ES256":
            # Supabase uses ES256 with JWKS public key
            jwks_data = await _get_jwks()
            kid = header.get("kid")
            matching_key = None
            for k in jwks_data.get("keys", []):
                if k.get("kid") == kid:
                    matching_key = k
                    break

            if not matching_key:
                raise JWTError("No matching JWKS key found")

            public_key = jwk.construct(matching_key, algorithm="ES256")
            payload = jwt.decode(
                token, public_key, algorithms=["ES256"], audience="authenticated"
            )
        else:
            # Fallback to HS256 with JWT secret
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_role(minimum_role: AdminRole):
    """Dependency that enforces a minimum admin role.

    Role hierarchy: staff < manager < owner
    """
    role_hierarchy = {
        AdminRole.STAFF: 0,
        AdminRole.MANAGER: 1,
        AdminRole.OWNER: 2,
    }

    async def role_checker(
        current_user: Annotated[AdminUser, Depends(get_current_user)],
    ) -> AdminUser:
        if role_hierarchy.get(current_user.role, -1) < role_hierarchy[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker


# Convenience type aliases
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[AdminUser, Depends(get_current_user)]
ManagerUser = Annotated[AdminUser, Depends(require_role(AdminRole.MANAGER))]
OwnerUser = Annotated[AdminUser, Depends(require_role(AdminRole.OWNER))]
