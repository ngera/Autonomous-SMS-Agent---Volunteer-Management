import uuid
from datetime import datetime

from pydantic import BaseModel


class VolunteersByService(BaseModel):
    service_name: str
    available: int  # volunteers who can participate
    min_per_slot: int  # minimum needed each occurrence
    max_per_slot: int  # maximum allowed each occurrence
    occurrences_30d: int  # how many times this service runs in 30 days
    buffer: int  # available - min_per_slot (how many can be absent and still meet min)
    buffer_pct: float  # buffer as percentage of min_per_slot


class DashboardSummary(BaseModel):
    todays_bookings_count: int
    unreviewed_suspensions_count: int
    suspended_or_banned_count: int
    monthly_bookings: int
    slots_needing_bookings: int
    total_volunteers: int
    volunteers_by_service: list[VolunteersByService]


class WeeklySlotStatus(BaseModel):
    """Status of a service within an availability window for a specific date."""
    date: str
    day_name: str
    window_label: str | None
    window_time: str
    service_name: str
    appointment_type_id: str
    min_required: int
    max_allowed: int
    booked: int
    status: str  # "needs_more", "met_minimum", "full"
    source: str  # "recurring" | "one_time"
    location: str | None = None
    last_reminder_sent: datetime | None = None
    last_announcement_sent: datetime | None = None


class TodaysBooking(BaseModel):
    id: uuid.UUID
    contact_phone: str
    contact_name: str | None
    appointment_type_name: str
    scheduled_at: datetime
    status: str


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    reference_id: uuid.UUID | None
    reference_type: str | None
    created_at: datetime
    read_at: datetime | None

    model_config = {"from_attributes": True}
