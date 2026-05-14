import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.contact import ContactSex, ContactStatus
from app.models.contact_consent import ConsentStatus


AvailabilitySlot = Literal[
    "weekday_am",
    "weekday_pm",
    "weekday_eve",
    "weekend_am",
    "weekend_pm",
    "weekend_eve",
]


class WeeklyHourBlock(BaseModel):
    day_of_week: int = Field(ge=0, le=6)  # 0=Monday..6=Sunday
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CustomerResponse(BaseModel):
    phone: str
    name: str | None
    email: str | None
    sex: ContactSex | None = None
    status: ContactStatus
    all_services_enabled: bool = False
    background_check_required: bool = False
    availability: list[AvailabilitySlot] = []
    weekly_hours: list[WeeklyHourBlock] = []
    unavailable_dates: list[date] = []
    total_minutes: int = 0
    reminder_preference_days: int
    consent_status: ConsentStatus | None = None
    preferred_appointment_type_ids: list[uuid.UUID] = []
    preferences: dict | None = None
    notes: str | None = None
    memory_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    phone: str
    name: str
    email: str | None = None
    sex: ContactSex | None = None
    all_services_enabled: bool = False
    background_check_required: bool = False
    availability: list[AvailabilitySlot] = []
    weekly_hours: list[WeeklyHourBlock] = []
    unavailable_dates: list[date] = []
    reminder_preference_days: int = 7
    preferred_appointment_type_ids: list[uuid.UUID] = []


class CustomerUpdate(BaseModel):
    phone: str | None = None
    name: str | None = None
    email: str | None = None
    sex: ContactSex | None = None
    all_services_enabled: bool | None = None
    background_check_required: bool | None = None
    availability: list[AvailabilitySlot] | None = None
    weekly_hours: list[WeeklyHourBlock] | None = None
    unavailable_dates: list[date] | None = None
    reminder_preference_days: int | None = None
    preferred_appointment_type_ids: list[uuid.UUID] | None = None
    preferences: dict | None = None
    notes: str | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    total_unfiltered: int
    page: int
    page_size: int


class ConsentHistoryResponse(BaseModel):
    id: uuid.UUID
    previous_status: ConsentStatus
    new_status: ConsentStatus
    changed_at: datetime
    changed_by_phone: str | None
    changed_by_admin_id: uuid.UUID | None
    reason: str | None

    model_config = {"from_attributes": True}


class OptOutRequest(BaseModel):
    reason: str


class OptInOutreachRequest(BaseModel):
    """Optional body for opt-in outreach."""
    pass


class PatternResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    appointment_type_id: uuid.UUID
    completed_booking_count: int
    calculated_interval_days: float | None
    blended_interval_days: float | None
    admin_default_days: float | None
    confidence: str
    outliers_removed: int
    manual_override_days: float | None
    last_calculated_at: datetime | None
    next_due_date: date | None

    model_config = {"from_attributes": True}


class PatternOverrideRequest(BaseModel):
    manual_override_days: float


class CsvImportResponse(BaseModel):
    imported: int
    updated: int = 0
    skipped: int
    errors: list[str]


class VolunteerServiceStat(BaseModel):
    appointment_type_id: uuid.UUID
    name: str
    category: str | None
    completed_bookings: int
    total_minutes: int


class VolunteerStatsResponse(BaseModel):
    total_completed_bookings: int
    total_minutes: int
    by_service: list[VolunteerServiceStat]


class VolunteerHoursSummary(BaseModel):
    total_minutes_all_time: int
    total_minutes_last_month: int
