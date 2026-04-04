import logging
import uuid
from datetime import date, datetime, time, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.dependencies import DbSession, SuperAdminUser
from app.models.admin_user import AdminRole, AdminUser
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.reminder import Reminder
from app.models.tenant import Tenant
from app.services.auth import _get_supabase_url
from app.schemas.tenant import (
    SuperAdminDashboardSummary,
    TenantCreate,
    TenantDetailResponse,
    TenantListResponse,
    TenantResponse,
    TenantSummaryItem,
    TenantUpdate,
)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


def _mask_secret(value: str | None, visible: int = 4) -> str | None:
    """Return a masked version of a secret, showing only the last `visible` chars."""
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def _build_detail_response(tenant: Tenant) -> TenantDetailResponse:
    data = TenantDetailResponse.model_validate(tenant, from_attributes=True)
    data.has_twilio = bool(tenant.twilio_account_sid)
    data.has_anthropic = bool(tenant.anthropic_api_key)
    data.has_google_calendar = bool(tenant.google_client_id)
    data.has_resend = bool(tenant.resend_api_key)
    data.twilio_account_sid_masked = _mask_secret(tenant.twilio_account_sid)
    data.twilio_auth_token_masked = _mask_secret(tenant.twilio_auth_token)
    data.anthropic_api_key_masked = _mask_secret(tenant.anthropic_api_key)
    data.google_client_id_masked = _mask_secret(tenant.google_client_id)
    data.google_client_secret_masked = _mask_secret(tenant.google_client_secret)
    data.google_refresh_token_masked = _mask_secret(tenant.google_refresh_token)
    data.resend_api_key_masked = _mask_secret(tenant.resend_api_key)
    return data


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    db: DbSession,
    current_user: SuperAdminUser,
    include_inactive: bool = Query(False),
    include_paused: bool = Query(True),
):
    query = select(Tenant)
    if not include_inactive:
        query = query.where(Tenant.is_active.is_(True))
    if not include_paused:
        query = query.where(Tenant.is_paused.is_(False))
    query = query.order_by(Tenant.name)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(query)
    tenants = result.scalars().all()
    return TenantListResponse(items=tenants, total=total)


@router.get("/dashboard/summary", response_model=SuperAdminDashboardSummary)
async def get_super_admin_dashboard(
    db: DbSession,
    current_user: SuperAdminUser,
    tenant_ids: str | None = Query(None, description="Comma-separated tenant UUIDs to filter"),
):
    """Cross-tenant dashboard summary for super admin."""
    today = date.today()
    first_of_month = today.replace(day=1)
    month_start = datetime.combine(first_of_month, time.min, tzinfo=timezone.utc)

    # Parse tenant_ids filter
    filter_ids: list[uuid.UUID] | None = None
    if tenant_ids:
        try:
            filter_ids = [uuid.UUID(tid.strip()) for tid in tenant_ids.split(",") if tid.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant_ids format")

    # Get all tenants (or filtered)
    tenant_query = select(Tenant)
    if filter_ids:
        tenant_query = tenant_query.where(Tenant.id.in_(filter_ids))
    result = await db.execute(tenant_query.order_by(Tenant.name))
    all_tenants = result.scalars().all()

    active_count = sum(1 for t in all_tenants if t.is_active and not t.is_paused)
    paused_count = sum(1 for t in all_tenants if t.is_active and t.is_paused)

    # Get tenant IDs for scoping queries
    scope_ids = [t.id for t in all_tenants]
    if not scope_ids:
        return SuperAdminDashboardSummary(
            total_tenants=0, active_tenants=0, paused_tenants=0,
            total_customers=0, total_bookings=0, total_conversations=0,
            total_reminders=0, total_revenue=0.0, tenants=[],
        )

    # Per-tenant stats
    tenant_items: list[TenantSummaryItem] = []
    total_customers = 0
    total_bookings = 0
    total_conversations = 0
    total_reminders = 0
    total_revenue = 0.0

    for t in all_tenants:
        cust_count = (await db.execute(
            select(func.count()).where(Contact.tenant_id == t.id)
        )).scalar() or 0

        book_count = (await db.execute(
            select(func.count()).where(
                Booking.tenant_id == t.id,
                Booking.created_at >= month_start,
                Booking.status != BookingStatus.CANCELLED,
            )
        )).scalar() or 0

        conv_count = (await db.execute(
            select(func.count()).where(
                Conversation.tenant_id == t.id,
                Conversation.created_at >= month_start,
            )
        )).scalar() or 0

        rem_count = (await db.execute(
            select(func.count()).where(
                Reminder.tenant_id == t.id,
                Reminder.scheduled_for >= first_of_month,
            )
        )).scalar() or 0

        rev = (await db.execute(
            select(func.coalesce(func.sum(Booking.price_at_booking), 0)).where(
                Booking.tenant_id == t.id,
                Booking.created_at >= month_start,
                Booking.status != BookingStatus.CANCELLED,
            )
        )).scalar() or 0

        total_customers += cust_count
        total_bookings += book_count
        total_conversations += conv_count
        total_reminders += rem_count
        total_revenue += float(rev)

        tenant_items.append(TenantSummaryItem(
            id=t.id, name=t.name, slug=t.slug,
            is_active=t.is_active, is_paused=t.is_paused,
            customers=cust_count, bookings=book_count,
            conversations=conv_count, reminders=rem_count,
            revenue=float(rev),
        ))

    return SuperAdminDashboardSummary(
        total_tenants=len(all_tenants),
        active_tenants=active_count,
        paused_tenants=paused_count,
        total_customers=total_customers,
        total_bookings=total_bookings,
        total_conversations=total_conversations,
        total_reminders=total_reminders,
        total_revenue=total_revenue,
        tenants=tenant_items,
    )


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return _build_detail_response(tenant)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate, db: DbSession, current_user: SuperAdminUser
):
    logger.info("create_tenant called with body: %s", body.model_dump(exclude={"admin_password"}))

    # Check slug uniqueness
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        logger.warning("Tenant slug '%s' already exists", body.slug)
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    # Extract admin credentials before creating tenant (not tenant model fields)
    admin_email = body.admin_email
    admin_password = body.admin_password
    tenant_data = body.model_dump(exclude={"admin_email", "admin_password"})
    logger.info("Creating tenant with data keys: %s", list(tenant_data.keys()))

    try:
        tenant = Tenant(**tenant_data)
        db.add(tenant)
        await db.flush()
        await db.refresh(tenant)
        logger.info("Tenant created: id=%s, name=%s", tenant.id, tenant.name)
    except Exception as e:
        logger.error("Failed to create tenant: %s", e, exc_info=True)
        await db.rollback()
        error_str = str(e)
        if "twilio_phone_number_key" in error_str:
            raise HTTPException(status_code=409, detail="Twilio phone number is already in use by another tenant")
        if "tenants_slug_key" in error_str:
            raise HTTPException(status_code=409, detail="Tenant slug already exists")
        raise HTTPException(status_code=400, detail=f"Failed to create tenant: {error_str}")

    # Create admin owner user for the tenant if credentials provided
    if admin_email and admin_password:
        logger.info("Creating admin user for tenant %s with email %s", tenant.id, admin_email)
        supabase_url = _get_supabase_url()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{supabase_url}/auth/v1/admin/users",
                    json={
                        "email": admin_email,
                        "password": admin_password,
                        "email_confirm": True,
                    },
                    headers={
                        "apikey": settings.supabase_service_key,
                        "Authorization": f"Bearer {settings.supabase_service_key}",
                        "Content-Type": "application/json",
                    },
                )
            logger.info("Supabase auth response: status=%s, body=%s", response.status_code, response.text)
        except Exception as e:
            logger.error("Supabase auth request failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Auth provider error: {e}")

        if response.status_code not in (200, 201):
            error_detail = response.json().get("msg", "Failed to create admin user in auth provider")
            logger.error("Supabase user creation failed: %s", error_detail)
            raise HTTPException(status_code=400, detail=error_detail)

        auth_user = response.json()
        user_id = uuid.UUID(auth_user["id"])
        logger.info("Supabase user created: id=%s", user_id)

        admin_user = AdminUser(
            id=user_id,
            tenant_id=tenant.id,
            email=admin_email,
            role=AdminRole.OWNER,
        )
        db.add(admin_user)
        await db.flush()
        logger.info("AdminUser record created for tenant %s", tenant.id)
    else:
        logger.info("No admin credentials provided, skipping admin user creation")

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
    tenant.deactivated_at = func.now()
    await db.flush()


@router.post("/{tenant_id}/pause", response_model=TenantResponse)
async def pause_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_active:
        raise HTTPException(status_code=400, detail="Cannot pause a deactivated tenant")
    if tenant.is_paused:
        raise HTTPException(status_code=400, detail="Tenant is already paused")

    tenant.is_paused = True
    tenant.paused_at = func.now()
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.post("/{tenant_id}/unpause", response_model=TenantResponse)
async def unpause_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_paused:
        raise HTTPException(status_code=400, detail="Tenant is not paused")

    tenant.is_paused = False
    tenant.paused_at = None
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.post("/{tenant_id}/reactivate", response_model=TenantResponse)
async def reactivate_tenant(
    tenant_id: uuid.UUID, db: DbSession, current_user: SuperAdminUser
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.is_active:
        raise HTTPException(status_code=400, detail="Tenant is already active")

    tenant.is_active = True
    tenant.deactivated_at = None
    tenant.is_paused = False
    tenant.paused_at = None
    await db.flush()
    await db.refresh(tenant)
    return tenant
