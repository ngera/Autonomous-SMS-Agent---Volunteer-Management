import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.reminder import ReminderStatus


class ReminderResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    appointment_type_id: uuid.UUID
    pattern_snapshot: dict | None
    scheduled_for: date
    sent_at: datetime | None
    follow_up_sent_at: datetime | None
    status: ReminderStatus
    converted_to_booking_id: uuid.UUID | None
    skip_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReminderListResponse(BaseModel):
    items: list[ReminderResponse]
    total: int


class ReminderTriggerRequest(BaseModel):
    contact_phone: str
    appointment_type_id: uuid.UUID


class ReminderCancelRequest(BaseModel):
    reason: str
