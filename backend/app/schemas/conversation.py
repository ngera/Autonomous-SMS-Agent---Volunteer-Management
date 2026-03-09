import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.conversation import ConversationStatus


class ConversationResponse(BaseModel):
    id: uuid.UUID
    contact_phone: str
    message_history: list[dict]
    current_step: str | None
    status: ConversationStatus
    consent_verified_at: datetime | None
    created_at: datetime
    last_message_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
