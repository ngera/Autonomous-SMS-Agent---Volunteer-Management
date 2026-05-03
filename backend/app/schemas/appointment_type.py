import uuid
from datetime import datetime

from pydantic import BaseModel


class AppointmentTypeCreate(BaseModel):
    name: str
    category: str | None = None
    duration_minutes: int
    price: float
    description: str | None = None
    recurrence_weeks_default: int | None = None
    is_active: bool = True


class AppointmentTypeUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    duration_minutes: int | None = None
    price: float | None = None
    description: str | None = None
    recurrence_weeks_default: int | None = None
    is_active: bool | None = None


class AppointmentTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    duration_minutes: int
    price: float
    description: str | None
    recurrence_weeks_default: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RelatedServiceCreate(BaseModel):
    related_appointment_type_id: uuid.UUID
    suggestion_message: str


class RelatedServiceResponse(BaseModel):
    id: uuid.UUID
    appointment_type_id: uuid.UUID
    related_appointment_type_id: uuid.UUID
    suggestion_message: str
    created_at: datetime

    model_config = {"from_attributes": True}
