import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.models.agent_call_log import AgentCallLog
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
