"""Cross-agent + per-volunteer frequency caps.

Skeleton in Path A. Real enforcement lands in the Phase 2 compliance
bundle (per path_a_agent_architecture_plan.md). The interface is here
now so agents can call it; today it returns "allow" for everything so
behavior is unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.tenant import Tenant

logger = get_logger("orchestrator.cooldown")


@dataclass(frozen=True)
class CooldownDecision:
    allow: bool
    reason: str  # for audit decision_reason
    retry_after: timedelta | None = None


async def check(
    db: AsyncSession,
    tenant: Tenant,
    contact: Contact | None,
) -> CooldownDecision:
    """Return whether an outbound send is allowed right now.

    Two policies:
      1. Cross-agent cooldown — contact.last_outbound_at vs
         tenant.cross_agent_cooldown_hours
      2. Per-volunteer weekly cap — rolling-7-day outbound count vs
         tenant.per_volunteer_weekly_cap

    Phase 1 (today): policy check returns allow=True; real enforcement
    deferred to the compliance bundle. Path is exercised so wiring is
    correct; toggling enforcement on later is a one-line change.
    """
    if contact is None:
        return CooldownDecision(allow=True, reason="no-contact")

    # TODO: enable in Phase 2 — until then this is observational only
    enforce = False
    if not enforce:
        return CooldownDecision(allow=True, reason="cooldown-not-enforced-yet")

    now = datetime.now(timezone.utc)
    cooldown_hours = int(getattr(tenant, "cross_agent_cooldown_hours", 24) or 24)
    if contact.last_outbound_at is not None:
        elapsed = now - contact.last_outbound_at
        if elapsed < timedelta(hours=cooldown_hours):
            return CooldownDecision(
                allow=False,
                reason=f"cross-agent-cooldown ({cooldown_hours}h)",
                retry_after=timedelta(hours=cooldown_hours) - elapsed,
            )
    return CooldownDecision(allow=True, reason="ok")


async def record_outbound(
    db: AsyncSession,
    contact: Contact,
) -> None:
    """Stamp last_outbound_at on the contact when an agent sends an SMS."""
    contact.last_outbound_at = datetime.now(timezone.utc)
    await db.flush()
