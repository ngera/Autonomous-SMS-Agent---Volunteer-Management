import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.availability import AvailabilityRule, SpecificDateSlot
from app.models.blocked_date import BlockedDate
from app.schemas.availability import (
    AvailabilityRuleResponse,
    BlockedDateCreate,
    BlockedDateResponse,
    SlotResponse,
    SpecificDateSlotCreate,
    SpecificDateSlotResponse,
    SpecificDateSlotUpdate,
    WeeklyScheduleUpdate,
)

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])


def _serialize_service_config(data: dict) -> dict:
    """Convert service_config Pydantic models to dicts with str UUIDs for JSONB."""
    if data.get("service_config"):
        data["service_config"] = [
            {
                "appointment_type_id": str(c["appointment_type_id"]),
                "min_required": c["min_required"],
                "max_allowed": c["max_allowed"],
            }
            for c in data["service_config"]
        ]
    return data


# ── Weekly rules ──

@router.get("/rules", response_model=list[AvailabilityRuleResponse])
async def get_availability_rules(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(AvailabilityRule)
        .where(AvailabilityRule.tenant_id == tenant.id)
        .order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
    )
    return result.scalars().all()


@router.put("/rules", response_model=list[AvailabilityRuleResponse])
async def update_availability_rules(
    body: WeeklyScheduleUpdate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    await db.execute(delete(AvailabilityRule).where(AvailabilityRule.tenant_id == tenant.id))
    new_rules = []
    for rule_data in body.rules:
        data = _serialize_service_config(rule_data.model_dump())
        rule = AvailabilityRule(tenant_id=tenant.id, **data)
        db.add(rule)
        new_rules.append(rule)
    await db.flush()
    for rule in new_rules:
        await db.refresh(rule)
    return new_rules


# ── Specific date slots / events ──

@router.get("/specific-slots", response_model=list[SpecificDateSlotResponse])
async def list_specific_date_slots(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(SpecificDateSlot)
        .where(SpecificDateSlot.tenant_id == tenant.id)
        .order_by(SpecificDateSlot.date, SpecificDateSlot.start_time)
    )
    return result.scalars().all()


@router.post("/specific-slots", response_model=SpecificDateSlotResponse, status_code=status.HTTP_201_CREATED)
async def create_specific_date_slot(
    body: SpecificDateSlotCreate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    data = _serialize_service_config(body.model_dump())
    slot = SpecificDateSlot(tenant_id=tenant.id, **data)
    db.add(slot)
    await db.flush()
    await db.refresh(slot)
    return slot


@router.put("/specific-slots/{slot_id}", response_model=SpecificDateSlotResponse)
async def update_specific_date_slot(
    slot_id: uuid.UUID,
    body: SpecificDateSlotUpdate,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id, SpecificDateSlot.tenant_id == tenant.id
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Specific date slot not found")

    update_data = _serialize_service_config(body.model_dump(exclude_unset=True))
    for field, value in update_data.items():
        setattr(slot, field, value)
    await db.flush()
    await db.refresh(slot)
    return slot


@router.delete("/specific-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specific_date_slot(
    slot_id: uuid.UUID, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id, SpecificDateSlot.tenant_id == tenant.id
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Specific date slot not found")
    await db.delete(slot)


# ── Blocked dates ──

@router.get("/blocked-dates", response_model=list[BlockedDateResponse])
async def get_blocked_dates(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(BlockedDate).where(BlockedDate.tenant_id == tenant.id).order_by(BlockedDate.date_from)
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
        select(BlockedDate).where(BlockedDate.id == blocked_id, BlockedDate.tenant_id == tenant.id)
    )
    blocked = result.scalar_one_or_none()
    if not blocked:
        raise HTTPException(status_code=404, detail="Blocked date not found")
    await db.delete(blocked)


# ── Slot preview ──

@router.get("/slots", response_model=list[SlotResponse])
async def get_available_slots(
    db: DbSession, current_user: CurrentUser, tenant: CurrentTenant,
    date_param: date = Query(..., alias="date"),
    appointment_type_id: uuid.UUID = Query(...),
):
    from app.services.availability import compute_available_slots
    return await compute_available_slots(
        db=db, target_date=date_param, appointment_type_id=str(appointment_type_id), tenant=tenant,
    )
