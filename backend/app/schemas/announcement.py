import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.announcement import AnnouncementStatus


class AnnouncementCreate(BaseModel):
    message: str
    filter_appointment_type_ids: list[uuid.UUID] | None = None
    scheduled_at: datetime | None = None


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
    created_by_admin_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int
