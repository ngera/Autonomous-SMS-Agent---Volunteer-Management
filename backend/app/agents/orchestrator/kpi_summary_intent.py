"""Orchestrator-level admin intent: "summary" / "how are things going".

On-demand recall of the same KPI digest the scheduler sends each
morning. Cross-domain (it spans recruitment, scheduling, and
campaigns), so it lives at the orchestrator level rather than inside
any single domain agent's admin_intents.

Routed by [admin_dispatch.maybe_handle_admin_command](backend/app/agents/orchestrator/admin_dispatch.py)
ahead of the LLM fallthrough — predictable cost, no Sonnet tokens
burned for a fixed-shape reply.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.kpi_summary import (
    compute_kpi_summary,
    format_kpi_summary_sms,
)

logger = get_logger("orchestrator.kpi_summary_intent")


# A handful of phrasings — every match goes to the same handler.
_PATTERNS = [
    re.compile(r"^\s*summary\s*\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*summary\s+status\s*\??\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*(what\s+is|what['’]?s)\s+the\s+(overall\s+)?(status|summary)\s*\??\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*how\s+(are|is)\s+(things|it)\s+going\s*\??\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*overall\s+status\s*\??\s*$", re.IGNORECASE),
]


def matches_kpi_summary_command(body: str) -> bool:
    b = (body or "").strip()
    if not b:
        return False
    return any(p.match(b) for p in _PATTERNS)


async def handle(
    db: AsyncSession,
    *,
    admin: AdminUser,
    message_body: str,
) -> str:
    """Return the SMS-formatted KPI digest for the admin's tenant.

    SUPER_ADMIN is handled upstream — if we're here, the admin has a
    valid tenant_id."""
    if admin.tenant_id is None:
        # Defensive: should never happen because Orchestrator filters
        # SUPER_ADMINs before delegating, but if it does we'd rather
        # return a soft message than crash.
        return (
            "Summary is per-tenant — switch to a tenant in the admin "
            "panel and try again."
        )

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == admin.tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        return "Tenant not found."

    summary = await compute_kpi_summary(db, tenant)
    return format_kpi_summary_sms(summary)


__all__ = [
    "matches_kpi_summary_command",
    "handle",
]
