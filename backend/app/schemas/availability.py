import uuid
from datetime import date as DateT, datetime, time

from pydantic import BaseModel, model_validator


class ServiceSlotConfig(BaseModel):
    """Per-service config within an availability window."""
    appointment_type_id: uuid.UUID
    min_required: int = 1
    max_allowed: int = 1

    @model_validator(mode="after")
    def validate_min_max(self):
        if self.min_required < 1:
            raise ValueError("min_required must be at least 1")
        if self.max_allowed < self.min_required:
            raise ValueError(f"max_allowed ({self.max_allowed}) must be >= min_required ({self.min_required})")
        return self


# ── Weekly rules ──

class AvailabilityRuleResponse(BaseModel):
    id: uuid.UUID
    day_of_week: int
    label: str | None
    location: str | None
    start_time: time
    end_time: time
    buffer_minutes: int
    service_config: list[ServiceSlotConfig] | None
    is_active: bool
    allow_roster_sharing: bool = True

    model_config = {"from_attributes": True}


class AvailabilityRuleUpdate(BaseModel):
    # Carrying `id` is what lets PUT /rules behave as a real upsert
    # (preserving rule identity + FK link from materialized slots)
    # instead of a destructive delete-and-recreate. None for new rows.
    id: uuid.UUID | None = None
    day_of_week: int
    label: str | None = None
    location: str | None = None
    start_time: time
    end_time: time
    buffer_minutes: int = 0
    service_config: list[ServiceSlotConfig] | None = None
    is_active: bool = True
    allow_roster_sharing: bool = True


class WeeklyScheduleUpdate(BaseModel):
    rules: list[AvailabilityRuleUpdate]


# ── Specific date slots / events ──

class SpecificDateSlotResponse(BaseModel):
    id: uuid.UUID
    date: DateT
    label: str | None
    location: str | None
    start_time: time
    end_time: time
    buffer_minutes: int
    service_config: list[ServiceSlotConfig] | None
    is_active: bool
    allow_roster_sharing: bool = True
    description: str | None = None
    availability_rule_id: uuid.UUID | None = None
    rule_drift_at: datetime | None = None
    rule_drift_summary: list[dict] | None = None

    model_config = {"from_attributes": True}


class SpecificDateSlotCreate(BaseModel):
    date: DateT
    label: str | None = None
    location: str | None = None
    start_time: time
    end_time: time
    buffer_minutes: int = 0
    service_config: list[ServiceSlotConfig] | None = None
    is_active: bool = True
    allow_roster_sharing: bool = True
    description: str | None = None


class SpecificDateSlotUpdate(BaseModel):
    date: DateT | None = None
    label: str | None = None
    location: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    buffer_minutes: int | None = None
    service_config: list[ServiceSlotConfig] | None = None
    is_active: bool | None = None
    allow_roster_sharing: bool | None = None
    description: str | None = None


# ── Blocked dates ──

class BlockedDateCreate(BaseModel):
    date_from: DateT
    date_to: DateT
    reason: str | None = None


class BlockedDateResponse(BaseModel):
    id: uuid.UUID
    date_from: DateT
    date_to: DateT
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SlotResponse(BaseModel):
    start: datetime
    end: datetime
    booked: int = 0
    min_required: int = 1
    max_allowed: int = 1
