"""Tenant-scoped Observability endpoints (decision #33).

Available to OWNER (always) and MANAGER (per per-tenant SystemSetting
`manager_can_see_observability`, default true). Implicitly scoped to
the requester's tenant via CurrentTenant.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.services import observability

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


class MetricResponse(BaseModel):
    label: str
    value: float
    numerator: int
    denominator: int
    extra: dict | None = None


def _window_from_days(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


@router.get("/phase1", response_model=list[MetricResponse])
async def phase1_metrics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(default=30, ge=1, le=365),
):
    """Bundle of all Phase 1 metrics for the current tenant.

    Window defaults to last 30 days; tenants can switch to 7 / 90 /
    custom via the `days` query param.
    """
    window_start, window_end = _window_from_days(days)
    results = []
    for fn in (
        observability.check_in_completion_rate,
        observability.admin_vs_volunteer_checkin_split,
        observability.auto_close_rate,
        observability.walkup_candidate_volume,
        observability.candidate_promote_dismiss_split,
    ):
        r = await fn(
            db, tenant_id=tenant.id, window_start=window_start, window_end=window_end
        )
        results.append(
            MetricResponse(
                label=r.label,
                value=r.value,
                numerator=r.numerator,
                denominator=r.denominator,
                extra=r.extra,
            )
        )
    return results


@router.get("/phase2", response_model=list[MetricResponse])
async def phase2_metrics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(default=30, ge=1, le=365),
):
    """Bundle of Phase 2 metrics — roster auto-ping health.

    Distinct endpoint so the UI can poll Phase 1 + Phase 2 separately
    (and future phases get their own endpoints by the same pattern).
    """
    window_start, window_end = _window_from_days(days)
    results = []
    for fn in (
        observability.pings_sent_volume,
        observability.stop_status_optout_rate,
        observability.all_checked_in_suppression_rate,
        observability.dispatch_failed_rate,
    ):
        r = await fn(
            db, tenant_id=tenant.id, window_start=window_start, window_end=window_end
        )
        results.append(
            MetricResponse(
                label=r.label,
                value=r.value,
                numerator=r.numerator,
                denominator=r.denominator,
                extra=r.extra,
            )
        )
    return results


@router.get("/phase3", response_model=list[MetricResponse])
async def phase3_metrics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(default=30, ge=1, le=365),
):
    """Bundle of Phase 3 metrics — service log + mid-event switch health."""
    window_start, window_end = _window_from_days(days)
    results = []
    for fn in (
        observability.switch_request_volume,
        observability.approval_rate,
        observability.supersede_rate,
        observability.approval_latency_seconds,
    ):
        r = await fn(
            db, tenant_id=tenant.id, window_start=window_start, window_end=window_end
        )
        results.append(
            MetricResponse(
                label=r.label,
                value=r.value,
                numerator=r.numerator,
                denominator=r.denominator,
                extra=r.extra,
            )
        )
    return results


@router.get("/phase4", response_model=list[MetricResponse])
async def phase4_metrics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(default=30, ge=1, le=365),
):
    """Bundle of Phase 4 metrics — post-event review + grading health."""
    window_start, window_end = _window_from_days(days)
    results = []
    for fn in (
        observability.review_approval_rate,
        observability.time_to_review_seconds,
        observability.grade_distribution,
        observability.consider_striking_rate,
        observability.owner_unlock_rate,
        observability.super_admin_unlock_rate,
    ):
        r = await fn(
            db, tenant_id=tenant.id, window_start=window_start, window_end=window_end
        )
        results.append(
            MetricResponse(
                label=r.label,
                value=r.value,
                numerator=r.numerator,
                denominator=r.denominator,
                extra=r.extra,
            )
        )
    return results


@router.get("/phase5", response_model=list[MetricResponse])
async def phase5_metrics(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(default=30, ge=1, le=365),
):
    """Bundle of Phase 5 metrics — recognition + quality-score distribution."""
    window_start, window_end = _window_from_days(days)
    results = []
    for fn in (
        observability.recognitions_earned_per_kind,
        observability.congrats_sms_dispatch_volume,
        observability.quality_score_distribution,
        observability.candidate_auto_prune_volume,
    ):
        r = await fn(
            db, tenant_id=tenant.id, window_start=window_start, window_end=window_end
        )
        results.append(
            MetricResponse(
                label=r.label,
                value=r.value,
                numerator=r.numerator,
                denominator=r.denominator,
                extra=r.extra,
            )
        )
    return results
