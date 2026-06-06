import uuid
from datetime import date as DateT, datetime, time

from pydantic import BaseModel

from app.models.booking import BookingStatus, RosterVisibility


class BookingCreate(BaseModel):
    contact_phone: str
    appointment_type_id: uuid.UUID
    scheduled_at: datetime
    price_at_booking: float
    roster_visibility: RosterVisibility = RosterVisibility.FIRST_NAME


class BookingResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    appointment_type_id: uuid.UUID
    scheduled_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    status: BookingStatus
    roster_visibility: RosterVisibility = RosterVisibility.FIRST_NAME
    price_at_booking: float
    calendar_event_id: str | None
    ics_sequence: int
    ics_new_url: str | None
    ics_update_url: str | None
    conversation_id: uuid.UUID | None
    created_at: datetime
    contact_name: str | None = None
    appointment_type_name: str | None = None
    duration_minutes: int | None = None

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


class EventRosterSignup(BaseModel):
    booking_id: uuid.UUID
    phone: str
    name: str | None
    status: BookingStatus
    scheduled_at: datetime


class EventRosterService(BaseModel):
    appointment_type_id: uuid.UUID
    name: str
    category: str
    min_required: int
    max_allowed: int
    signups: list[EventRosterSignup]


class EventRosterEvent(BaseModel):
    source: str  # "specific_date" | "weekly_rule" | "ad_hoc"
    source_id: uuid.UUID | None = None  # SpecificDateSlot.id / AvailabilityRule.id
    label: str | None = None
    location: str | None = None
    date: DateT
    start_time: time
    end_time: time


class EventRosterHistoryEntry(BaseModel):
    """One row in the roster's combined audit feed.

    Spans every booking in the slot — creations, status changes,
    reschedules, cancellations — so an admin gets one chronological
    log of who did what to which booking when.
    """
    timestamp: datetime
    event_type: str  # mirrors BookingEventType.value
    booking_id: uuid.UUID
    volunteer_name: str | None
    volunteer_phone: str
    service_name: str
    previous_scheduled_at: datetime | None = None
    new_scheduled_at: datetime | None = None
    previous_status: str | None = None
    new_status: str | None = None
    changed_by: str  # 'user_sms' | 'admin' | 'scheduler'
    admin_email: str | None = None
    notes: str | None = None


class EventRosterResponse(BaseModel):
    event: EventRosterEvent | None
    services: list[EventRosterService]
    history: list[EventRosterHistoryEntry] = []
