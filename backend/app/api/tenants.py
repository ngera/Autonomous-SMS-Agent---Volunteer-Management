import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.dependencies import DbSession, SuperAdminUser
from app.models.tenant import Tenant
from app.schemas.tenant import (
    TenantCreate,
    TenantDetailResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    db: DbSession,
    current_user: SuperAdminUser,
    include_inactive: bool = Query(False),
):
    query = select(Tenant)
    if not include_inactive:
        query = query.where(Tenant.is_active.is_(True))
    query = query.order_by(Tenant.name)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(query)
    tenants = result.scalars().all()
    return TenantListResponse(items=tenants, total=total)


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        business_name=tenant.business_name,
        business_domain=tenant.business_domain,
        business_timezone=tenant.business_timezone,
        admin_panel_url=tenant.admin_panel_url,
        api_domain=tenant.api_domain,
        twilio_phone_number=tenant.twilio_phone_number,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        has_twilio=bool(tenant.twilio_account_sid),
        has_anthropic=bool(tenant.anthropic_api_key),
        has_google_calendar=bool(tenant.google_client_id),
        has_resend=bool(tenant.resend_api_key),
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate, db: DbSession, current_user: SuperAdminUser
):
    # Check slug uniqueness
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    tenant = Tenant(**body.model_dump())
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    db: DbSession,
    current_user: SuperAdminUser,
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_data = body.model_dump(exclude_unset=True)

    # Check slug uniqueness if changing
    if "slug" in update_data and update_data["slug"] != tenant.slug:
        existing = await db.execute(
            select(Tenant).where(Tenant.slug == update_data["slug"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="Tenant slug already exists"
            )

    for key, value in update_data.items():
        setattr(tenant, key, value)

    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.is_active = False
    await db.flush()
