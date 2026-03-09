import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    contact_phone: str
    appointment_type_id: uuid.UUID
    scheduled_at: datetime
    price_at_booking: float


class BookingResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    appointment_type_id: uuid.UUID
    scheduled_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    status: BookingStatus
    price_at_booking: float
    calendar_event_id: str | None
    ics_sequence: int
    ics_new_url: str | None
    ics_update_url: str | None
    conversation_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    total: int
    page: int
    page_size: int


class RescheduleRequest(BaseModel):
    new_scheduled_at: datetime


class StatusUpdateRequest(BaseModel):
    status: BookingStatus
    notes: str | None = None


class BookingHistoryResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    event_type: str
    previous_scheduled_at: datetime | None
    new_scheduled_at: datetime | None
    previous_status: BookingStatus | None
    new_status: BookingStatus | None
    changed_by: str
    changed_by_admin_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
