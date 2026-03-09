import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.suspension import ReviewDecision, SuspensionType


class SuspensionResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    suspended_at: datetime
    suspension_type: SuspensionType
    reason: str
    strike_ids: list[uuid.UUID] | None
    conversation_id: uuid.UUID | None
    notification_sent_at: datetime | None
    reviewed_by_admin_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_decision: ReviewDecision | None
    review_notes: str | None
    lifted_at: datetime | None

    model_config = {"from_attributes": True}


class SuspensionListResponse(BaseModel):
    items: list[SuspensionResponse]
    total: int


class ReviewRequest(BaseModel):
    notes: str


class ManualSuspendRequest(BaseModel):
    reason: str
