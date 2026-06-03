import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete as sql_delete, func, select, update

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.agent_call_log import AgentCallLog
from app.models.booking import Booking
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.suspension import ContactSuspension
from app.models.token_usage import TokenUsage
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


class BulkDeleteRequest(BaseModel):
    """Filter criteria for bulk-deleting conversations.

    At least one of `older_than`, `contact_phone`, or `ids` must be set.
    When multiple are provided, they're AND-ed together.
    """
    older_than: datetime | None = None
    contact_phone: str | None = None
    ids: list[uuid.UUID] | None = None


class BulkDeleteResponse(BaseModel):
    deleted_count: int


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_conversations(
    body: BulkDeleteRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Bulk-delete conversations matching the given filters.

    FK-referenced rows on bookings, suspensions, and token_usage are
    preserved — their `conversation_id` is nulled out so the audit trail
    survives. `agent_call_log` rows for deleted conversations are removed
    (they're trace data, not history).

    Requires MANAGER+ role. Tenant-scoped — only the caller's tenant's
    conversations are considered regardless of the IDs sent.
    """
    if not (body.older_than or body.contact_phone or body.ids):
        raise HTTPException(
            status_code=400,
            detail="At least one of older_than, contact_phone, or ids must be provided.",
        )

    # Resolve target conversation IDs under the tenant scope first, so the
    # downstream FK nulls / deletes operate on a known set.
    target_query = select(Conversation.id).where(
        Conversation.tenant_id == tenant.id
    )
    if body.older_than is not None:
        target_query = target_query.where(
            Conversation.last_message_at < body.older_than
        )
    if body.contact_phone:
        target_query = target_query.where(
            Conversation.contact_phone == body.contact_phone
        )
    if body.ids:
        target_query = target_query.where(Conversation.id.in_(body.ids))

    target_ids = [row for row in (await db.execute(target_query)).scalars().all()]
    if not target_ids:
        return BulkDeleteResponse(deleted_count=0)

    # NULL out FK refs on rows we want to preserve (audit trail).
    for model_cls in (Booking, ContactSuspension, TokenUsage):
        await db.execute(
            update(model_cls)
            .where(model_cls.conversation_id.in_(target_ids))
            .values(conversation_id=None)
        )

    # Drop trace events — they're tied to the conversation, not history.
    await db.execute(
        sql_delete(AgentCallLog).where(
            AgentCallLog.conversation_id.in_(target_ids)
        )
    )

    # Finally delete the conversations.
    result = await db.execute(
        sql_delete(Conversation).where(Conversation.id.in_(target_ids))
    )
    await db.commit()

    return BulkDeleteResponse(deleted_count=result.rowcount or len(target_ids))


@router.get("/{conversation_id}/trace")
async def get_conversation_trace(
    conversation_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    limit: int = Query(200, ge=1, le=1000),
):
    """Graph-shaped trace of agent activity for one conversation.

    Returns the rows from agent_call_log scoped to this conversation,
    grouped by ``turn_id``. The frontend Trace tab renders these as a
    per-turn timeline of routing decisions, agent invocations, tool
    calls, and LLM calls.

    Tenant-scoped: the conversation MUST belong to the caller's tenant
    or 404. Defense in depth — agent_call_log rows for other tenants
    are also tenant-filtered.
    """
    # Verify the conversation belongs to this tenant
    conv = (await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = (await db.execute(
        select(AgentCallLog)
        .where(
            AgentCallLog.conversation_id == conversation_id,
            AgentCallLog.tenant_id == tenant.id,
        )
        .order_by(AgentCallLog.created_at.asc())
        .limit(limit)
    )).scalars().all()

    # Group by turn_id while preserving order
    turns: dict[str, list[dict]] = {}
    for row in rows:
        turn_key = str(row.turn_id)
        if turn_key not in turns:
            turns[turn_key] = []
        turns[turn_key].append({
            "id": str(row.id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_agent": row.source_agent,
            "destination_agent": row.destination_agent,
            "event_type": row.event_type,
            "decision_reason": row.decision_reason,
            "state_snapshot": row.state_snapshot,
            "tool_name": row.tool_name,
            "tool_input": row.tool_input,
            "tool_output_summary": row.tool_output_summary,
            "model_used": row.model_used,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "latency_ms": row.latency_ms,
            "status": row.status,
            "error_message": row.error_message,
        })

    # Preserve insertion order (turns ordered by the first row's
    # created_at, which is the order we already pulled them in)
    return {
        "conversation_id": str(conversation_id),
        "turns": [
            {"turn_id": tid, "events": events}
            for tid, events in turns.items()
        ],
        "total_events": len(rows),
    }
