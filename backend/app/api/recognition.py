"""Phase 5 — Recognition admin API.

Endpoints:
  GET    /api/v1/recognition/definitions       — list definitions
  POST   /api/v1/recognition/definitions       — create
  PUT    /api/v1/recognition/definitions/{id}  — update (label/desc/auto_criteria/is_active)
  DELETE /api/v1/recognition/definitions/{id}  — soft-deactivate (is_active=false)
  POST   /api/v1/recognition/grant             — admin manual grant
  GET    /api/v1/recognition/contact/{id}      — volunteer's recognition history

Definitions CRUD is OWNER+ only (these change scoring rules). Manual
grants are MANAGER+ since admins routinely grant per-event awards
(e.g. "MVP of Saturday Food Drive").
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.dependencies import (
    CurrentTenant,
    CurrentUser,
    DbSession,
    ManagerUser,
    OwnerUser,
)
from app.models.award_definition import (
    AWARD_KIND_AWARD,
    AWARD_KIND_BADGE,
    AWARD_KIND_MILESTONE,
    AWARD_SCOPE_LIFETIME,
    AWARD_SCOPE_PER_EVENT,
    AWARD_SCOPE_PER_PERIOD,
    AwardDefinition,
    PERIOD_UNIT_MONTH,
    PERIOD_UNIT_QUARTER,
    PERIOD_UNIT_YEAR,
)
from app.models.volunteer_recognition import VolunteerRecognition
from app.services.recognition_engine import manual_grant

router = APIRouter(prefix="/api/v1/recognition", tags=["recognition"])


# ── Schemas ────────────────────────────────────────────────────────


class DefinitionCreate(BaseModel):
    kind: str  # milestone | badge | award
    key: str
    label: str
    description: str | None = None
    icon_key: str | None = None
    auto_criteria: dict | None = None
    uniqueness_scope: str = AWARD_SCOPE_LIFETIME
    period_unit: str | None = None


class DefinitionUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    icon_key: str | None = None
    auto_criteria: dict | None = None
    is_active: bool | None = None


class DefinitionResponse(BaseModel):
    id: uuid.UUID
    kind: str
    key: str
    label: str
    description: str | None
    icon_key: str | None
    auto_criteria: dict | None
    uniqueness_scope: str
    period_unit: str | None
    is_active: bool
    created_at: datetime


class GrantRequest(BaseModel):
    contact_id: uuid.UUID
    definition_id: uuid.UUID
    earned_via_slot_id: uuid.UUID | None = None
    notes: str | None = None


class RecognitionResponse(BaseModel):
    id: uuid.UUID
    definition_id: uuid.UUID
    definition_label: str
    definition_kind: str
    definition_icon_key: str | None
    earned_at: datetime
    period_key: str | None
    earned_via_slot_id: uuid.UUID | None
    granted_by_admin_id: uuid.UUID | None
    notes: str | None


def _to_definition_response(d: AwardDefinition) -> DefinitionResponse:
    return DefinitionResponse(
        id=d.id,
        kind=d.kind,
        key=d.key,
        label=d.label,
        description=d.description,
        icon_key=d.icon_key,
        auto_criteria=d.auto_criteria,
        uniqueness_scope=d.uniqueness_scope,
        period_unit=d.period_unit,
        is_active=d.is_active,
        created_at=d.created_at,
    )


# ── Validation helpers ────────────────────────────────────────────


_VALID_KINDS = {AWARD_KIND_MILESTONE, AWARD_KIND_BADGE, AWARD_KIND_AWARD}
_VALID_SCOPES = {AWARD_SCOPE_LIFETIME, AWARD_SCOPE_PER_EVENT, AWARD_SCOPE_PER_PERIOD}
_VALID_PERIODS = {PERIOD_UNIT_MONTH, PERIOD_UNIT_QUARTER, PERIOD_UNIT_YEAR}
_VALID_METRICS = {"hours", "events_completed", "service_count", "avg_grade_over_last_n"}


def _validate_definition_payload(body: DefinitionCreate) -> None:
    if body.kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid kind; allowed: {_VALID_KINDS}")
    if body.uniqueness_scope not in _VALID_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid uniqueness_scope; allowed: {_VALID_SCOPES}",
        )
    if body.uniqueness_scope == AWARD_SCOPE_PER_PERIOD:
        if body.period_unit not in _VALID_PERIODS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "uniqueness_scope='per_period' requires period_unit "
                    f"in {_VALID_PERIODS}"
                ),
            )
    else:
        if body.period_unit is not None:
            raise HTTPException(
                status_code=400,
                detail="period_unit only valid when uniqueness_scope='per_period'",
            )

    # Decision #7 — kind ⇄ auto_criteria validation:
    if body.kind == AWARD_KIND_MILESTONE and not body.auto_criteria:
        raise HTTPException(
            status_code=400,
            detail="milestone kind requires auto_criteria",
        )
    if body.auto_criteria is not None:
        metric = body.auto_criteria.get("metric")
        if metric not in _VALID_METRICS:
            raise HTTPException(
                status_code=400,
                detail=f"auto_criteria.metric must be one of {_VALID_METRICS}",
            )


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/definitions", response_model=list[DefinitionResponse])
async def list_definitions(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    include_inactive: bool = False,
):
    """List definitions for the current tenant (active-only by default)."""
    stmt = select(AwardDefinition).where(AwardDefinition.tenant_id == tenant.id)
    if not include_inactive:
        stmt = stmt.where(AwardDefinition.is_active.is_(True))
    stmt = stmt.order_by(AwardDefinition.kind, AwardDefinition.label)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_definition_response(d) for d in rows]


@router.post(
    "/definitions",
    response_model=DefinitionResponse,
    status_code=201,
)
async def create_definition(
    body: DefinitionCreate,
    db: DbSession,
    current_user: OwnerUser,
    tenant: CurrentTenant,
):
    """Create a new definition. OWNER+ only — changing scoring rules
    is a tenant-policy action."""
    _validate_definition_payload(body)
    # Check unique constraint up front for a friendly 400.
    existing = (
        await db.execute(
            select(AwardDefinition).where(
                AwardDefinition.tenant_id == tenant.id,
                AwardDefinition.key == body.key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail=f"definition with key='{body.key}' already exists",
        )

    definition = AwardDefinition(
        tenant_id=tenant.id,
        kind=body.kind,
        key=body.key,
        label=body.label,
        description=body.description,
        icon_key=body.icon_key,
        auto_criteria=body.auto_criteria,
        uniqueness_scope=body.uniqueness_scope,
        period_unit=body.period_unit,
        is_active=True,
    )
    db.add(definition)
    await db.flush()
    return _to_definition_response(definition)


@router.put("/definitions/{definition_id}", response_model=DefinitionResponse)
async def update_definition(
    definition_id: uuid.UUID,
    body: DefinitionUpdate,
    db: DbSession,
    current_user: OwnerUser,
    tenant: CurrentTenant,
):
    """Update mutable fields. kind / key / uniqueness_scope / period_unit
    are intentionally NOT mutable — changing those would break existing
    recognition rows' uniqueness semantics."""
    definition = (
        await db.execute(
            select(AwardDefinition).where(
                AwardDefinition.id == definition_id,
                AwardDefinition.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="definition not found")

    if body.label is not None:
        definition.label = body.label
    if body.description is not None:
        definition.description = body.description
    if body.icon_key is not None:
        definition.icon_key = body.icon_key
    if body.auto_criteria is not None:
        # Validate metric if present.
        metric = body.auto_criteria.get("metric")
        if metric is not None and metric not in _VALID_METRICS:
            raise HTTPException(
                status_code=400,
                detail=f"auto_criteria.metric must be one of {_VALID_METRICS}",
            )
        definition.auto_criteria = body.auto_criteria
    if body.is_active is not None:
        definition.is_active = body.is_active

    await db.flush()
    return _to_definition_response(definition)


@router.delete("/definitions/{definition_id}", status_code=204)
async def deactivate_definition(
    definition_id: uuid.UUID,
    db: DbSession,
    current_user: OwnerUser,
    tenant: CurrentTenant,
):
    """Soft-deactivate — historical recognitions stay; new evaluations
    skip this definition."""
    definition = (
        await db.execute(
            select(AwardDefinition).where(
                AwardDefinition.id == definition_id,
                AwardDefinition.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="definition not found")
    definition.is_active = False
    await db.flush()


@router.post("/grant", response_model=RecognitionResponse, status_code=201)
async def grant_recognition(
    body: GrantRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Admin manually grants a recognition. Honors per-event /
    per-period scope dedup — returns 409 if already granted."""
    try:
        row = await manual_grant(
            db,
            tenant_id=tenant.id,
            contact_id=body.contact_id,
            definition_id=body.definition_id,
            granted_by_admin_id=current_user.id,
            earned_via_slot_id=body.earned_via_slot_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="recognition already exists for this contact at this scope",
        )

    # Resolve definition for response.
    definition = (
        await db.execute(
            select(AwardDefinition).where(AwardDefinition.id == row.definition_id)
        )
    ).scalar_one()
    return RecognitionResponse(
        id=row.id,
        definition_id=row.definition_id,
        definition_label=definition.label,
        definition_kind=definition.kind,
        definition_icon_key=definition.icon_key,
        earned_at=row.earned_at,
        period_key=row.period_key,
        earned_via_slot_id=row.earned_via_slot_id,
        granted_by_admin_id=row.granted_by_admin_id,
        notes=row.notes,
    )


@router.get("/contact/{contact_id}", response_model=list[RecognitionResponse])
async def list_recognitions_for_contact(
    contact_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """List all recognitions a contact has earned. Sorted recent-first."""
    rows = (
        await db.execute(
            select(VolunteerRecognition, AwardDefinition)
            .join(
                AwardDefinition,
                VolunteerRecognition.definition_id == AwardDefinition.id,
            )
            .where(
                VolunteerRecognition.tenant_id == tenant.id,
                VolunteerRecognition.contact_id == contact_id,
            )
            .order_by(VolunteerRecognition.earned_at.desc())
        )
    ).all()
    return [
        RecognitionResponse(
            id=r.id,
            definition_id=r.definition_id,
            definition_label=d.label,
            definition_kind=d.kind,
            definition_icon_key=d.icon_key,
            earned_at=r.earned_at,
            period_key=r.period_key,
            earned_via_slot_id=r.earned_via_slot_id,
            granted_by_admin_id=r.granted_by_admin_id,
            notes=r.notes,
        )
        for r, d in rows
    ]
