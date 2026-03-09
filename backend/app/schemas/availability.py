import uuid
from datetime import date, datetime, time

from pydantic import BaseModel


class AvailabilityRuleResponse(BaseModel):
    id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    buffer_minutes: int
    is_active: bool

    model_config = {"from_attributes": True}


class AvailabilityRuleUpdate(BaseModel):
    """A single day's schedule for the weekly update."""
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    buffer_minutes: int = 0
    is_active: bool = True


class WeeklyScheduleUpdate(BaseModel):
    rules: list[AvailabilityRuleUpdate]


class BlockedDateCreate(BaseModel):
    date_from: date
    date_to: date
    reason: str | None = None


class BlockedDateResponse(BaseModel):
    id: uuid.UUID
    date_from: date
    date_to: date
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SlotResponse(BaseModel):
    start: datetime
    end: datetime
