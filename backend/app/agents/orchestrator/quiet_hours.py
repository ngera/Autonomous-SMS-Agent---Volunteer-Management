"""Volunteer-local quiet-hours enforcement.

Skeleton in Path A — defers to allow-everything until Phase 2 compliance
bundle. Real check: convert tenant.quiet_hours_start/end into the
volunteer's local timezone (contact.timezone, falls back to tenant.business_timezone),
and reject if current time is inside the window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.tenant import Tenant


@dataclass(frozen=True)
class QuietHoursDecision:
    allow: bool
    reason: str


async def check(
    db: AsyncSession,
    tenant: Tenant,
    contact: Contact | None,
) -> QuietHoursDecision:
    """Returns allow=True today; real enforcement in Phase 2.

    See path_a_agent_architecture_plan.md — Phase 2 compliance bundle.
    """
    return QuietHoursDecision(allow=True, reason="quiet-hours-not-enforced-yet")
