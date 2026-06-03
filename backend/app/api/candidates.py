"""Walk-up candidates admin API (Phase 1 step 5d).

Endpoints:
  GET    /api/v1/candidates             — list candidates for tenant
  POST   /api/v1/candidates/{id}/invite  — promote: create Contact +
                                            ContactConsent(PENDING) +
                                            trigger recruiter invite flow
  POST   /api/v1/candidates/{id}/dismiss — mark dismissed
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ConsentStatus, ContactConsent, OptInMethod
from app.models.volunteer_candidate import (
    CANDIDATE_STATUS_DISMISSED,
    CANDIDATE_STATUS_INVITED,
    VolunteerCandidate,
)

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


# ── Schemas ──────────────────────────────────────────────────────────


class CandidateResponse(BaseModel):
    id: uuid.UUID
    phone: str
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    last_signal_slot_id: uuid.UUID | None
    last_message_body: str | None
    status: str
    invited_at: datetime | None
    dismissed_at: datetime | None
    promoted_contact_id: uuid.UUID | None


class InviteRequest(BaseModel):
    name: str  # required


class DismissRequest(BaseModel):
    notes: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    status_filter: str | None = None,
):
    """List candidates for the current tenant. Optional status filter."""
    q = select(VolunteerCandidate).where(VolunteerCandidate.tenant_id == tenant.id)
    if status_filter:
        q = q.where(VolunteerCandidate.status == status_filter)
    q = q.order_by(VolunteerCandidate.last_seen_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/{candidate_id}/invite", response_model=CandidateResponse)
async def invite_candidate(
    candidate_id: uuid.UUID,
    body: InviteRequest,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Promote a candidate to a real Contact.

    Creates Contact + ContactConsent(PENDING) and links via
    `promoted_contact_id`. The actual recruiter invite SMS is dispatched
    by the existing recruiter flow once consent is opt-in.
    """
    result = await db.execute(
        select(VolunteerCandidate).where(
            VolunteerCandidate.id == candidate_id,
            VolunteerCandidate.tenant_id == tenant.id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "new":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot invite a candidate in status='{candidate.status}'",
        )

    # Reuse an existing Contact if one happens to match (rare — would only
    # happen if a Contact got created out-of-band after candidate capture).
    contact_q = await db.execute(
        select(Contact).where(
            Contact.tenant_id == tenant.id,
            Contact.phone == candidate.phone,
        )
    )
    contact = contact_q.scalar_one_or_none()
    if contact is None:
        contact = Contact(
            tenant_id=tenant.id,
            phone=candidate.phone,
            name=body.name,
            status=ContactStatus.ACTIVE,
        )
        db.add(contact)
        await db.flush()
        db.add(
            ContactConsent(
                tenant_id=tenant.id,
                contact_id=contact.id,
                contact_phone=candidate.phone,
                status=ConsentStatus.PENDING,
            )
        )

    # Stamp candidate as invited.
    candidate.status = CANDIDATE_STATUS_INVITED
    candidate.invited_at = datetime.now(timezone.utc)
    candidate.invited_by_admin_id = current_user.id
    candidate.promoted_contact_id = contact.id
    await db.flush()
    return candidate


@router.post("/{candidate_id}/dismiss", response_model=CandidateResponse)
async def dismiss_candidate(
    candidate_id: uuid.UUID,
    body: DismissRequest,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Mark a candidate as dismissed. Row preserved for audit (1-year cap)."""
    result = await db.execute(
        select(VolunteerCandidate).where(
            VolunteerCandidate.id == candidate_id,
            VolunteerCandidate.tenant_id == tenant.id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "new":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dismiss a candidate in status='{candidate.status}'",
        )

    candidate.status = CANDIDATE_STATUS_DISMISSED
    candidate.dismissed_at = datetime.now(timezone.utc)
    candidate.dismissed_by_admin_id = current_user.id
    if body.notes:
        candidate.notes = body.notes
    await db.flush()
    return candidate
