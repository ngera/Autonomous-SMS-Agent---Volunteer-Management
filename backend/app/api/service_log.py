"""Phase 3 — booking_service_log admin API.

Endpoints:
  GET  /api/v1/service-log/pending/{slot_id}  — pending entries for run-sheet UI
  POST /api/v1/service-log/{id}/approve        — admin Approve from UI
  POST /api/v1/service-log/{id}/reject         — admin Reject from UI

Approve/Reject use optimistic concurrency: the client sends the
expected `version`, and the backend rejects with 409 if the row
has moved (likely supersede race).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking
from app.models.booking_service_log import (
    BSL_STATUS_PENDING,
    BookingServiceLog,
)
from app.models.contact import Contact
from app.services.service_log import (
    OptimisticLockError,
    approve_pending,
    reject_pending,
)

router = APIRouter(prefix="/api/v1/service-log", tags=["service-log"])


class PendingEntryResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    contact_name: str | None
    contact_phone: str
    target_service: str  # appointment_type.name being requested
    created_at: datetime
    version: int


class ApproveRejectRequest(BaseModel):
    expected_version: int
    reason: str | None = None  # only used on reject


class EntryStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    version: int
    approved_at: datetime | None


@router.get("/pending/{slot_id}", response_model=list[PendingEntryResponse])
async def list_pending_for_slot(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """List all pending service_log entries for the bookings on one slot.

    Used by the run-sheet page's "Pending approvals" panel.
    """
    result = await db.execute(
        select(BookingServiceLog, Contact, AppointmentType, Booking)
        .join(Booking, BookingServiceLog.booking_id == Booking.id)
        .join(Contact, Booking.contact_id == Contact.id)
        .join(
            AppointmentType,
            BookingServiceLog.appointment_type_id == AppointmentType.id,
        )
        .where(
            BookingServiceLog.tenant_id == tenant.id,
            BookingServiceLog.status == BSL_STATUS_PENDING,
            Booking.event_slot_id == slot_id,
        )
        .order_by(BookingServiceLog.created_at.desc())
    )
    rows = []
    for entry, contact, appt, booking in result.all():
        rows.append(
            PendingEntryResponse(
                id=entry.id,
                booking_id=booking.id,
                contact_name=contact.name,
                contact_phone=contact.phone,
                target_service=appt.name,
                created_at=entry.created_at,
                version=entry.version,
            )
        )
    return rows


@router.post("/{entry_id}/approve", response_model=EntryStatusResponse)
async def approve_entry(
    entry_id: uuid.UUID,
    body: ApproveRejectRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Approve a pending entry. Returns 409 on optimistic-version race
    (supersede happened between client read and write).
    """
    # Scope-check via the entry's tenant_id.
    pre = await db.execute(
        select(BookingServiceLog).where(
            BookingServiceLog.id == entry_id,
            BookingServiceLog.tenant_id == tenant.id,
        )
    )
    if pre.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    try:
        entry = await approve_pending(
            db,
            entry_id=entry_id,
            expected_version=body.expected_version,
            admin=current_user,
        )
    except OptimisticLockError:
        raise HTTPException(
            status_code=409,
            detail="Stale version — request was modified (likely superseded). Refresh.",
        )

    return EntryStatusResponse(
        id=entry.id,
        status=entry.status,
        version=entry.version,
        approved_at=entry.approved_at,
    )


@router.post("/{entry_id}/reject", response_model=EntryStatusResponse)
async def reject_entry(
    entry_id: uuid.UUID,
    body: ApproveRejectRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Reject a pending entry. Same 409 semantics as approve."""
    pre = await db.execute(
        select(BookingServiceLog).where(
            BookingServiceLog.id == entry_id,
            BookingServiceLog.tenant_id == tenant.id,
        )
    )
    if pre.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    try:
        entry = await reject_pending(
            db,
            entry_id=entry_id,
            expected_version=body.expected_version,
            admin=current_user,
            reason=body.reason,
        )
    except OptimisticLockError:
        raise HTTPException(
            status_code=409,
            detail="Stale version — request was modified (likely superseded). Refresh.",
        )

    return EntryStatusResponse(
        id=entry.id,
        status=entry.status,
        version=entry.version,
        approved_at=entry.approved_at,
    )
