import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DbSession, ManagerUser
from app.models.appointment_type import AppointmentType
from app.models.related_service import RelatedService
from app.schemas.appointment_type import (
    AppointmentTypeCreate,
    AppointmentTypeResponse,
    AppointmentTypeUpdate,
    RelatedServiceCreate,
    RelatedServiceResponse,
)

router = APIRouter(prefix="/api/v1/appointment-types", tags=["appointment-types"])


@router.get("", response_model=list[AppointmentTypeResponse])
async def list_appointment_types(db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(AppointmentType).order_by(AppointmentType.name)
    )
    return result.scalars().all()


@router.post("", response_model=AppointmentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment_type(
    body: AppointmentTypeCreate, db: DbSession, current_user: ManagerUser
):
    appt_type = AppointmentType(**body.model_dump())
    db.add(appt_type)
    await db.flush()
    await db.refresh(appt_type)
    return appt_type


@router.put("/{type_id}", response_model=AppointmentTypeResponse)
async def update_appointment_type(
    type_id: uuid.UUID, body: AppointmentTypeUpdate, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == type_id)
    )
    appt_type = result.scalar_one_or_none()
    if not appt_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(appt_type, field, value)

    await db.flush()
    await db.refresh(appt_type)
    return appt_type


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_appointment_type(
    type_id: uuid.UUID, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(AppointmentType).where(AppointmentType.id == type_id)
    )
    appt_type = result.scalar_one_or_none()
    if not appt_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    appt_type.is_active = False
    await db.flush()


@router.get("/{type_id}/related", response_model=list[RelatedServiceResponse])
async def list_related_services(
    type_id: uuid.UUID, db: DbSession, current_user: CurrentUser
):
    result = await db.execute(
        select(RelatedService).where(RelatedService.appointment_type_id == type_id)
    )
    return result.scalars().all()


@router.post("/{type_id}/related", response_model=RelatedServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_related_service(
    type_id: uuid.UUID, body: RelatedServiceCreate, db: DbSession, current_user: ManagerUser
):
    related = RelatedService(
        appointment_type_id=type_id,
        related_appointment_type_id=body.related_appointment_type_id,
        suggestion_message=body.suggestion_message,
    )
    db.add(related)
    await db.flush()
    await db.refresh(related)
    return related


@router.delete("/{type_id}/related/{related_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_related_service(
    type_id: uuid.UUID, related_id: uuid.UUID, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(RelatedService).where(
            RelatedService.id == related_id,
            RelatedService.appointment_type_id == type_id,
        )
    )
    related = result.scalar_one_or_none()
    if not related:
        raise HTTPException(status_code=404, detail="Related service not found")

    await db.delete(related)
