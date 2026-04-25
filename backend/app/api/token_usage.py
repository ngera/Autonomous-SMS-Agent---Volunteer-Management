from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import aliased

from app.core.dependencies import CurrentTenant, DbSession, ManagerUser
from app.models.contact import Contact
from app.models.token_usage import TokenUsage, TokenUsageSource
from app.schemas.token_usage import (
    TokenUsageByDay,
    TokenUsageByModel,
    TokenUsageBySource,
    TokenUsageByTool,
    TokenUsageByVolunteer,
    TokenUsageDashboard,
    TokenUsageDetail,
    TokenUsageSummary,
)

router = APIRouter(prefix="/api/v1/token-usage", tags=["token-usage"])

# Pricing per 1M tokens
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
}
DEFAULT_PRICING = {"input": 1.00, "output": 5.00}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


@router.get("/dashboard", response_model=TokenUsageDashboard)
async def get_token_usage_dashboard(
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    days: int = Query(30, ge=1, le=90),
):
    """Get comprehensive token usage analytics with drill-downs."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_filter = [TokenUsage.tenant_id == tenant.id, TokenUsage.created_at >= cutoff]

    # ── Summary ──
    summary_result = await db.execute(
        select(
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output"),
            func.count().label("requests"),
        ).where(*base_filter)
    )
    row = summary_result.one()
    total_input = int(row.input)
    total_output = int(row.output)

    # ── By model (also calculates total cost) ──
    model_result = await db.execute(
        select(
            TokenUsage.model,
            func.sum(TokenUsage.input_tokens).label("input"),
            func.sum(TokenUsage.output_tokens).label("output"),
            func.count().label("requests"),
        )
        .where(*base_filter)
        .group_by(TokenUsage.model)
    )
    by_model = []
    total_cost = 0.0
    for m in model_result.all():
        cost = _estimate_cost(m.model, int(m.input), int(m.output))
        total_cost += cost
        by_model.append(TokenUsageByModel(
            model=m.model,
            input_tokens=int(m.input),
            output_tokens=int(m.output),
            total_tokens=int(m.input) + int(m.output),
            request_count=int(m.requests),
        ))

    summary = TokenUsageSummary(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        total_requests=int(row.requests),
        estimated_cost_usd=round(total_cost, 4),
    )

    # ── By source ──
    source_result = await db.execute(
        select(
            TokenUsage.source,
            func.sum(TokenUsage.input_tokens).label("input"),
            func.sum(TokenUsage.output_tokens).label("output"),
            func.count().label("requests"),
        )
        .where(*base_filter)
        .group_by(TokenUsage.source)
    )
    by_source = [
        TokenUsageBySource(
            source=r.source.value,
            input_tokens=int(r.input),
            output_tokens=int(r.output),
            total_tokens=int(r.input) + int(r.output),
            request_count=int(r.requests),
        )
        for r in source_result.all()
    ]

    # ── Daily breakdown ──
    daily_result = await db.execute(
        select(
            func.to_char(TokenUsage.created_at, "YYYY-MM-DD").label("date"),
            func.sum(TokenUsage.input_tokens).label("input"),
            func.sum(TokenUsage.output_tokens).label("output"),
            func.count().label("requests"),
        )
        .where(*base_filter)
        .group_by("date")
        .order_by("date")
    )
    daily = [
        TokenUsageByDay(
            date=r.date,
            input_tokens=int(r.input),
            output_tokens=int(r.output),
            total_tokens=int(r.input) + int(r.output),
            request_count=int(r.requests),
        )
        for r in daily_result.all()
    ]

    # ── By volunteer (contact) ──
    vol_result = await db.execute(
        select(
            TokenUsage.contact_id,
            TokenUsage.contact_phone,
            Contact.name.label("contact_name"),
            TokenUsage.model,
            func.sum(TokenUsage.input_tokens).label("input"),
            func.sum(TokenUsage.output_tokens).label("output"),
            func.count().label("requests"),
        )
        .outerjoin(Contact, TokenUsage.contact_id == Contact.id)
        .where(*base_filter, TokenUsage.contact_id.is_not(None))
        .group_by(TokenUsage.contact_id, TokenUsage.contact_phone, Contact.name, TokenUsage.model)
    )
    # Aggregate per-contact across models (need to sum costs per model)
    volunteer_map: dict[str, dict] = {}
    for r in vol_result.all():
        cid = str(r.contact_id)
        inp, out = int(r.input), int(r.output)
        cost = _estimate_cost(r.model, inp, out)
        if cid not in volunteer_map:
            volunteer_map[cid] = {
                "contact_id": cid,
                "contact_phone": r.contact_phone,
                "contact_name": r.contact_name,
                "input_tokens": 0, "output_tokens": 0,
                "request_count": 0, "estimated_cost_usd": 0.0,
            }
        v = volunteer_map[cid]
        v["input_tokens"] += inp
        v["output_tokens"] += out
        v["request_count"] += int(r.requests)
        v["estimated_cost_usd"] += cost

    by_volunteer = sorted(
        [
            TokenUsageByVolunteer(
                total_tokens=v["input_tokens"] + v["output_tokens"],
                estimated_cost_usd=round(v["estimated_cost_usd"], 4),
                **{k: v[k] for k in ("contact_id", "contact_phone", "contact_name", "input_tokens", "output_tokens", "request_count")},
            )
            for v in volunteer_map.values()
        ],
        key=lambda x: x.total_tokens,
        reverse=True,
    )[:50]

    # ── By tool (from JSONB tool_calls) ──
    tool_result = await db.execute(
        text("""
            SELECT
                tool_elem->>'tool' AS tool_name,
                COUNT(*) AS call_count,
                COUNT(DISTINCT tu.id) AS request_count
            FROM token_usage tu,
                 jsonb_array_elements(tu.tool_calls) AS tool_elem
            WHERE tu.tenant_id = :tid
              AND tu.created_at >= :cutoff
              AND tu.tool_calls IS NOT NULL
              AND jsonb_typeof(tu.tool_calls) = 'array'
            GROUP BY tool_name
            ORDER BY call_count DESC
        """),
        {"tid": tenant.id, "cutoff": cutoff},
    )
    by_tool = [
        TokenUsageByTool(
            tool_name=r.tool_name,
            call_count=int(r.call_count),
            request_count=int(r.request_count),
        )
        for r in tool_result.all()
    ]

    # Add screener as a "tool" entry
    screener_count = await db.execute(
        select(func.count()).where(
            TokenUsage.tenant_id == tenant.id,
            TokenUsage.created_at >= cutoff,
            TokenUsage.source == TokenUsageSource.SCREENER,
        )
    )
    screener_total = int(screener_count.scalar() or 0)
    if screener_total > 0:
        by_tool.append(TokenUsageByTool(
            tool_name="screener",
            call_count=screener_total,
            request_count=screener_total,
        ))
        by_tool.sort(key=lambda x: x.call_count, reverse=True)

    # ── Recent entries ──
    recent_result = await db.execute(
        select(
            TokenUsage.id,
            TokenUsage.source,
            TokenUsage.model,
            TokenUsage.input_tokens,
            TokenUsage.output_tokens,
            TokenUsage.contact_phone,
            TokenUsage.tool_calls,
            TokenUsage.created_at,
            Contact.name.label("contact_name"),
        )
        .outerjoin(Contact, TokenUsage.contact_id == Contact.id)
        .where(*base_filter)
        .order_by(TokenUsage.created_at.desc())
        .limit(50)
    )
    recent = [
        TokenUsageDetail(
            id=str(r.id),
            source=r.source.value,
            model=r.model,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            contact_phone=r.contact_phone,
            contact_name=r.contact_name,
            tool_names=[tc.get("tool", "") for tc in (r.tool_calls or [])],
            created_at=r.created_at,
        )
        for r in recent_result.all()
    ]

    return TokenUsageDashboard(
        summary=summary,
        by_source=by_source,
        by_model=by_model,
        daily=daily,
        by_volunteer=by_volunteer,
        by_tool=by_tool,
        recent=recent,
    )
