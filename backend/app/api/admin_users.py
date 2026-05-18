import uuid

import httpx
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.models.admin_user import AdminRole, AdminUser
from app.schemas.settings import (
    AdminUserCreate,
    AdminUserPasswordUpdate,
    AdminUserResponse,
    AdminUserUpdate,
)
from app.services.auth import _get_supabase_url

router = APIRouter(prefix="/api/v1/admin-users", tags=["admin-users"])


def _require_owner_or_super(current_user: AdminUser) -> None:
    """Ensure the caller is at least OWNER (or SUPER_ADMIN)."""
    hierarchy = {
        AdminRole.STAFF: 0,
        AdminRole.MANAGER: 1,
        AdminRole.OWNER: 2,
        AdminRole.SUPER_ADMIN: 3,
    }
    if hierarchy.get(current_user.role, -1) < hierarchy[AdminRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


@router.get("", response_model=list[AdminUserResponse])
async def list_admin_users(
    db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    _require_owner_or_super(current_user)
    result = await db.execute(
        select(AdminUser).where(AdminUser.tenant_id == tenant.id).order_by(AdminUser.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    body: AdminUserCreate, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    _require_owner_or_super(current_user)

    # Validate role
    try:
        role = AdminRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    # Non-super-admins cannot create super_admin users
    if role == AdminRole.SUPER_ADMIN and current_user.role != AdminRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can create super admin users")

    # Create user in Supabase Auth
    supabase_url = _get_supabase_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{supabase_url}/auth/v1/admin/users",
            json={
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
            },
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code not in (200, 201):
        error_detail = response.json().get("msg", "Failed to create user in auth provider")
        raise HTTPException(status_code=400, detail=error_detail)

    auth_user = response.json()
    user_id = uuid.UUID(auth_user["id"])

    # Create admin user record
    admin_user = AdminUser(
        id=user_id,
        tenant_id=tenant.id,
        email=body.email,
        role=role,
        phone=(body.phone or None) if body.phone is not None else None,
    )
    db.add(admin_user)
    try:
        await db.flush()
    except IntegrityError as err:
        await db.rollback()
        if "ix_admin_users_tenant_phone" in str(err.orig) or "tenant_phone" in str(err):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Another admin in this tenant already uses that phone "
                    "number."
                ),
            )
        raise
    await db.refresh(admin_user)
    return admin_user


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    _require_owner_or_super(current_user)

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id, AdminUser.tenant_id == tenant.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    if body.role is not None:
        try:
            new_role = AdminRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        if new_role == AdminRole.SUPER_ADMIN and current_user.role != AdminRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only super admins can assign super admin role")
        user.role = new_role

    if body.is_active is not None:
        user.is_active = body.is_active

    # Phone is in AdminUserUpdate but was previously dropped on the floor.
    # ``model_fields_set`` lets us distinguish "not provided" (leave as-is)
    # from "explicitly cleared" (empty string → store as NULL so the
    # uniqueness constraint doesn't choke on multiple empty phones).
    if "phone" in body.model_fields_set:
        new_phone = body.phone.strip() if body.phone else None
        user.phone = new_phone or None

    try:
        await db.flush()
    except IntegrityError as err:
        await db.rollback()
        if "ix_admin_users_tenant_phone" in str(err.orig) or "tenant_phone" in str(err):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Another admin in this tenant already uses that phone "
                    "number."
                ),
            )
        raise
    await db.refresh(user)
    return user


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_admin_user_password(
    user_id: uuid.UUID,
    body: AdminUserPasswordUpdate,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    _require_owner_or_super(current_user)

    # Verify user belongs to this tenant
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id, AdminUser.tenant_id == tenant.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    # Update password in Supabase Auth
    supabase_url = _get_supabase_url()
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{supabase_url}/auth/v1/admin/users/{user_id}",
            json={"password": body.password},
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code not in (200, 201):
        error_detail = response.json().get("msg", "Failed to update password")
        raise HTTPException(status_code=400, detail=error_detail)
