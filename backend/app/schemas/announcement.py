import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.announcement import AnnouncementStatus, RecipientScope


class EventContext(BaseModel):
    """Snapshot of event details to render in the announcement header."""
    event_label: str | None = None
    event_date: str | None = None  # YYYY-MM-DD
    event_start_time: str | None = None  # HH:MM
    event_end_time: str | None = None  # HH:MM
    event_location: str | None = None
    service_name: str | None = None
    appointment_type_id: str | None = None


class AnnouncementCreate(BaseModel):
    message: str
    filter_appointment_type_ids: list[uuid.UUID] | None = None
    scheduled_at: datetime | None = None
    event_context: EventContext | None = None
    recipient_scope: RecipientScope = RecipientScope.ALL


class AnnouncementResponse(BaseModel):
    id: uuid.UUID
    message: str
    filter_appointment_type_ids: list[uuid.UUID] | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    status: AnnouncementStatus
    total_recipients: int
    sent_count: int
    failed_count: int
    event_context: EventContext | None = None
    recipient_scope: RecipientScope = RecipientScope.ALL
    created_by_admin_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int
