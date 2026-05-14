import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AppointmentTypeCreate(BaseModel):
    name: str
    category: str = Field(min_length=1)
    duration_minutes: int
    price: float
    description: str | None = None
    is_active: bool = True

    @field_validator("category")
    @classmethod
    def _category_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("category is required")
        return v


class AppointmentTypeUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    duration_minutes: int | None = None
    price: float | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("category")
    @classmethod
    def _category_not_blank(cls, v: str | None) -> str | None:
        # None means "field omitted" (Pydantic skips validation for unset
        # defaults). If the caller explicitly provides null or whitespace,
        # reject — category cannot be cleared.
        if v is None:
            raise ValueError("category cannot be null")
        v = v.strip()
        if not v:
            raise ValueError("category cannot be blank")
        return v


class AppointmentTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    duration_minutes: int
    price: float
    description: str | None
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
