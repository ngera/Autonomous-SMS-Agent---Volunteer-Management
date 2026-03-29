import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.availability import AvailabilityRule
from app.models.blocked_date import BlockedDate
from app.schemas.availability import (
    AvailabilityRuleResponse,
    BlockedDateCreate,
    BlockedDateResponse,
    SlotResponse,
    WeeklyScheduleUpdate,
)

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])


@router.get("/rules", response_model=list[AvailabilityRuleResponse])
async def get_availability_rules(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(AvailabilityRule)
        .where(AvailabilityRule.tenant_id == tenant.id)
        .order_by(AvailabilityRule.day_of_week)
    )
    return result.scalars().all()


@router.put("/rules", response_model=list[AvailabilityRuleResponse])
async def update_availability_rules(
    body: WeeklyScheduleUpdate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    # Delete existing rules for this tenant and replace with new ones
    await db.execute(
        delete(AvailabilityRule).where(AvailabilityRule.tenant_id == tenant.id)
    )

    new_rules = []
    for rule_data in body.rules:
        rule = AvailabilityRule(tenant_id=tenant.id, **rule_data.model_dump())
        db.add(rule)
        new_rules.append(rule)

    await db.flush()
    for rule in new_rules:
        await db.refresh(rule)
    return new_rules


@router.get("/blocked-dates", response_model=list[BlockedDateResponse])
async def get_blocked_dates(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(BlockedDate)
        .where(BlockedDate.tenant_id == tenant.id)
        .order_by(BlockedDate.date_from)
    )
    return result.scalars().all()


@router.post("/blocked-dates", response_model=BlockedDateResponse, status_code=status.HTTP_201_CREATED)
async def create_blocked_date(
    body: BlockedDateCreate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    blocked = BlockedDate(tenant_id=tenant.id, **body.model_dump())
    db.add(blocked)
    await db.flush()
    await db.refresh(blocked)
    return blocked


@router.delete("/blocked-dates/{blocked_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blocked_date(
    blocked_id: uuid.UUID, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(BlockedDate).where(
            BlockedDate.id == blocked_id, BlockedDate.tenant_id == tenant.id
        )
    )
    blocked = result.scalar_one_or_none()
    if not blocked:
        raise HTTPException(status_code=404, detail="Blocked date not found")

    await db.delete(blocked)


@router.get("/slots", response_model=list[SlotResponse])
async def get_available_slots(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    date_param: date = Query(..., alias="date"),
    appointment_type_id: uuid.UUID = Query(...),
):
    """Query available slots for a given date and appointment type."""
    from app.services.availability import compute_available_slots

    slots = await compute_available_slots(
        db=db,
        target_date=date_param,
        appointment_type_id=str(appointment_type_id),
        tenant=tenant,
    )
    return slots
