import uuid

import httpx
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import DbSession, OwnerUser
from app.models.admin_user import AdminRole, AdminUser
from app.schemas.settings import AdminUserCreate, AdminUserResponse, AdminUserUpdate
from app.services.auth import _get_supabase_url

router = APIRouter(prefix="/api/v1/admin-users", tags=["admin-users"])


@router.get("", response_model=list[AdminUserResponse])
async def list_admin_users(db: DbSession, current_user: OwnerUser):
    result = await db.execute(
        select(AdminUser).order_by(AdminUser.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    body: AdminUserCreate, db: DbSession, current_user: OwnerUser
):
    # Validate role
    try:
        role = AdminRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

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
        email=body.email,
        role=role,
    )
    db.add(admin_user)
    await db.flush()
    await db.refresh(admin_user)
    return admin_user


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    db: DbSession,
    current_user: OwnerUser,
):
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    if body.role is not None:
        try:
            user.role = AdminRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()
    await db.refresh(user)
    return user
