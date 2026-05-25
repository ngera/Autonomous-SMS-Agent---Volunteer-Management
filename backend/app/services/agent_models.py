"""Per-seam model selection for the agent architecture.

Each agent + each LLM seam declares its preferred model. The product
default split is Sonnet for multi-turn reasoning + planning + narrative,
Haiku for routing decisions + intent classification + screener-style
classifier work — see memory/path_a_agent_architecture_plan.md.

Per-tenant overrides live in ``tenants.agent_models`` JSONB. Resolution
order for any seam:
  1. tenant.agent_models[seam] if set
  2. RECOMMENDED_DEFAULTS[seam]
  3. existing per-tenant ai_model SystemSetting (back-compat with the
     pre-Path-A code which used one model everywhere)
  4. DEFAULT_MODEL (env / config default)
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tool_executor import DEFAULT_MODEL
from app.models.tenant import Tenant


# ── Canonical seam keys ──
# Use string constants so callers don't typo. Document each seam's
# intended role so model-recommendation drift is visible in code review.
SEAM_ORCHESTRATOR_CRISIS = "orchestrator_crisis"
SEAM_ORCHESTRATOR_INTENT_DISAMBIG = "orchestrator_intent_disambig"
SEAM_RECRUITER_SCHEDULER_CONVERSATION = "recruiter_scheduler_conversation"
SEAM_RECRUITER_SCHEDULER_INTENT_ROUTER = "recruiter_scheduler_intent_router"
SEAM_SCREENER = "screener"
SEAM_PLANNER_RECRUITMENT = "planner_recruitment"
SEAM_REPORTER_RECRUITMENT = "reporter_recruitment"
SEAM_ENGAGEMENT_PLANNER = "engagement_planner"
SEAM_ENGAGEMENT_REPORTER = "engagement_reporter"
SEAM_ENGAGEMENT_INTENT_ROUTER = "engagement_intent_router"
SEAM_PLANNER_MARKETING = "planner_marketing"
SEAM_REPORTER_MARKETING = "reporter_marketing"


# ── Recommended defaults ──
# Sonnet 4.6 for reasoning seams (multi-turn convo, planning, narrative).
# Haiku 4.5 for fast/cheap classifier + routing seams.
#
# These defaults are conservative — they don't UPGRADE existing tenants
# automatically. A tenant who hasn't set agent_models still gets their
# legacy ai_model SystemSetting (which is Haiku today everywhere). The
# defaults below kick in only for seams that have no prior assignment
# AND no tenant override.
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

RECOMMENDED_DEFAULTS: dict[str, str] = {
    # Multi-turn reasoning + planning + narrative → Sonnet
    SEAM_RECRUITER_SCHEDULER_CONVERSATION: SONNET,
    SEAM_PLANNER_RECRUITMENT: SONNET,
    SEAM_REPORTER_RECRUITMENT: SONNET,
    SEAM_ENGAGEMENT_REPORTER: SONNET,
    SEAM_PLANNER_MARKETING: SONNET,
    SEAM_REPORTER_MARKETING: SONNET,
    # Routing + classifier + intent → Haiku
    SEAM_ORCHESTRATOR_CRISIS: HAIKU,
    SEAM_ORCHESTRATOR_INTENT_DISAMBIG: HAIKU,
    SEAM_RECRUITER_SCHEDULER_INTENT_ROUTER: HAIKU,
    SEAM_SCREENER: HAIKU,
    SEAM_ENGAGEMENT_PLANNER: HAIKU,
    SEAM_ENGAGEMENT_INTENT_ROUTER: HAIKU,
}


async def resolve_model(
    db: AsyncSession,
    tenant: Tenant | None,
    seam: str,
) -> str:
    """Resolve which model to use for a given seam.

    Phase 1 (today): existing get_ai_model() callers are NOT migrated.
    This resolver is here so new code can adopt per-seam selection
    without breaking the pre-existing single-model behavior. Once the
    super-admin UI for per-seam config lands, existing callers
    progressively migrate over.
    """
    # 1. Tenant override
    if tenant is not None:
        overrides = getattr(tenant, "agent_models", None) or {}
        override = overrides.get(seam) if isinstance(overrides, dict) else None
        if override:
            return override

    # 2. Recommended default for this seam
    if seam in RECOMMENDED_DEFAULTS:
        # 2a. But fall back to the tenant's legacy ai_model setting if
        # it's set — back-compat means we don't surprise an existing
        # tenant by silently upgrading their cost.
        legacy = await _legacy_tenant_model(db, tenant)
        if legacy is not None:
            return legacy
        return RECOMMENDED_DEFAULTS[seam]

    # 3. Legacy / unknown seam: use the existing ai_model resolution
    legacy = await _legacy_tenant_model(db, tenant)
    return legacy if legacy is not None else DEFAULT_MODEL


async def _legacy_tenant_model(
    db: AsyncSession, tenant: Tenant | None
) -> str | None:
    """The pre-Path-A model resolution: ai_model SystemSetting."""
    if tenant is None:
        return None
    from sqlalchemy import select
    from app.models.system_setting import SystemSetting

    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key == "ai_model",
        )
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None
