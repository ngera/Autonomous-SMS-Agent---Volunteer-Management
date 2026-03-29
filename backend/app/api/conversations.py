from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationListResponse, ConversationResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Conversation).where(Conversation.tenant_id == tenant.id)

    if search:
        search_filter = f"%{search}%"
        query = query.join(
            Contact, Conversation.contact_phone == Contact.phone
        ).where(
            (Contact.phone.ilike(search_filter))
            | (Contact.name.ilike(search_filter))
        )

    query = query.order_by(Conversation.last_message_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return ConversationListResponse(items=items, total=total)
