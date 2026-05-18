"""Pydantic schemas for the Recruitment Agent REST API."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.recruitment_campaign import (
    CampaignStatus,
    ReportChannel,
    WaveStatus,
)


# ── Goal / policy ──


class CampaignGoal(BaseModel):
    appointment_type_id: uuid.UUID
    min_required: int = Field(..., ge=1)
    max_allowed: int | None = Field(default=None, ge=1)


# ── Create / approve / patch ──


class CampaignCreate(BaseModel):
    event_slot_id: uuid.UUID
    goals: list[CampaignGoal] | None = None  # auto-derived from slot if omitted


class CampaignPlanPatch(BaseModel):
    """Pre-approval edits to the plan."""
    policy: dict | None = None
    message_templates: dict | None = None


# ── Responses ──


class WaveResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    wave_number: int
    appointment_type_id: uuid.UUID
    status: WaveStatus
    scheduled_at: datetime
    targeted_contact_ids: list[uuid.UUID] | None = None
    selection_reason: str | None = None
    announcement_id: uuid.UUID | None = None
    sent_count: int
    signups_attributed: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    id: uuid.UUID
    report_date: date
    narrative: str | None
    sent_via: ReportChannel
    delivered_at: datetime | None

    model_config = {"from_attributes": True}


class CampaignResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    event_slot_id: uuid.UUID
    status: CampaignStatus
    goals: list[dict]
    policy: dict
    plan_summary: str | None
    plan_preview: dict | None
    message_templates: dict | None
    created_by_admin_id: uuid.UUID
    approved_by_admin_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignDetailResponse(CampaignResponse):
    waves: list[WaveResponse] = []
    recent_reports: list[ReportSummary] = []
    current_signups: dict[str, int] = {}  # service_id → count


class CampaignListItem(BaseModel):
    """Row for the Campaigns list page."""
    id: uuid.UUID
    event_slot_id: uuid.UUID
    event_label: str | None
    event_date: date
    days_to_event: int
    status: CampaignStatus
    fill_per_service: dict[str, dict]  # {service_id: {signups, target, name}}
    overall_fill_pct: float
    last_wave_sent_at: datetime | None
    next_wave_due_at: datetime | None
    at_risk: bool


class CampaignListResponse(BaseModel):
    items: list[CampaignListItem]
    aggregate: dict
    total: int
