import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    todays_bookings_count: int
    pending_conversations_count: int
    reminders_today_count: int
    unreviewed_suspensions_count: int
    monthly_bookings: int
    monthly_revenue: float
    opt_in_rate: float
    reminder_conversion_rate: float


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
