"""Phase 4 — booking review admin API.

Endpoints:
  GET    /api/v1/reviews/event/{slot_id}     — list reviews for one event
  POST   /api/v1/reviews/{id}/approve         — admin approves + grades
  POST   /api/v1/reviews/{id}/skip            — admin marks 'skipped' (no grade)
  POST   /api/v1/reviews/{id}/flip-no-show    — flip no_show → pending
  POST   /api/v1/reviews/{id}/unlock          — OWNER 24h grace + SUPER_ADMIN

Approval mutates contacts.historical_quality_score downstream; the
service-layer recompute fires synchronously inside approve_review().
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.booking_review import BookingReview
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.services.booking_review import (
    ReviewImmutableError,
    approve_review,
    can_unlock_review,
    flip_no_show_to_pending,
    skip_review,
    unlock_review,
)

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


# ── Schemas ────────────────────────────────────────────────────────


class ReviewSegment(BaseModel):
    in_: datetime | None = None
    out: datetime | None = None
    source_in: str | None = None
    source_out: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str | None
    status: str
    grade: int | None
    grade_notes: str | None
    total_hours: float | None
    segments: list[dict] | None
    final_check_in_at: datetime | None
    final_check_out_at: datetime | None
    reviewed_at: datetime | None
    unlocked_at: datetime | None
    unlock_count: int


class ApproveRequest(BaseModel):
    grade: int
    grade_notes: str | None = None


class SkipRequest(BaseModel):
    notes: str | None = None


def _to_response(
    review: BookingReview, contact: Contact
) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        booking_id=review.booking_id,
        contact_id=contact.id,
        contact_name=contact.name,
        status=review.status,
        grade=review.grade,
        grade_notes=review.grade_notes,
        total_hours=float(review.total_hours) if review.total_hours is not None else None,
        segments=review.segments,
        final_check_in_at=review.final_check_in_at,
        final_check_out_at=review.final_check_out_at,
        reviewed_at=review.reviewed_at,
        unlocked_at=review.unlocked_at,
        unlock_count=review.unlock_count,
    )


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/event/{slot_id}", response_model=list[ReviewResponse])
async def list_reviews_for_event(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """List all reviews (any status) for the bookings on one event slot.
    Used by the per-event review page."""
    result = await db.execute(
        select(BookingReview, Contact)
        .join(Booking, BookingReview.booking_id == Booking.id)
        .join(Contact, Booking.contact_id == Contact.id)
        .where(
            BookingReview.tenant_id == tenant.id,
            Booking.event_slot_id == slot_id,
            Booking.status != BookingStatus.CANCELLED,
        )
        .order_by(Contact.name)
    )
    return [_to_response(r, c) for r, c in result.all()]


@router.post("/{review_id}/approve", response_model=ReviewResponse)
async def approve_review_endpoint(
    review_id: uuid.UUID,
    body: ApproveRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    review = (
        await db.execute(
            select(BookingReview).where(
                BookingReview.id == review_id,
                BookingReview.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    try:
        review = await approve_review(
            db,
            review=review,
            grade=body.grade,
            grade_notes=body.grade_notes,
            admin=current_user,
        )
    except (ReviewImmutableError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    booking = (
        await db.execute(select(Booking).where(Booking.id == review.booking_id))
    ).scalar_one()
    contact = (
        await db.execute(select(Contact).where(Contact.id == booking.contact_id))
    ).scalar_one()
    return _to_response(review, contact)


@router.post("/{review_id}/skip", response_model=ReviewResponse)
async def skip_review_endpoint(
    review_id: uuid.UUID,
    body: SkipRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    review = (
        await db.execute(
            select(BookingReview).where(
                BookingReview.id == review_id,
                BookingReview.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    try:
        review = await skip_review(
            db, review=review, admin=current_user, notes=body.notes
        )
    except ReviewImmutableError as e:
        raise HTTPException(status_code=400, detail=str(e))

    booking = (
        await db.execute(select(Booking).where(Booking.id == review.booking_id))
    ).scalar_one()
    contact = (
        await db.execute(select(Contact).where(Contact.id == booking.contact_id))
    ).scalar_one()
    return _to_response(review, contact)


@router.post("/{review_id}/flip-no-show", response_model=ReviewResponse)
async def flip_no_show_endpoint(
    review_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    review = (
        await db.execute(
            select(BookingReview).where(
                BookingReview.id == review_id,
                BookingReview.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    try:
        review = await flip_no_show_to_pending(
            db, review=review, admin=current_user
        )
    except ReviewImmutableError as e:
        raise HTTPException(status_code=400, detail=str(e))

    booking = (
        await db.execute(select(Booking).where(Booking.id == review.booking_id))
    ).scalar_one()
    contact = (
        await db.execute(select(Contact).where(Contact.id == booking.contact_id))
    ).scalar_one()
    return _to_response(review, contact)


@router.post("/{review_id}/unlock", response_model=ReviewResponse)
async def unlock_review_endpoint(
    review_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    review = (
        await db.execute(
            select(BookingReview).where(
                BookingReview.id == review_id,
                BookingReview.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    # Need the slot to compute the 24h grace window for OWNER.
    booking = (
        await db.execute(select(Booking).where(Booking.id == review.booking_id))
    ).scalar_one()
    slot = (
        await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.id == booking.event_slot_id
            )
        )
    ).scalar_one()

    if not can_unlock_review(
        review, slot, current_user, tenant.business_timezone
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Unlock denied. SUPER_ADMIN always allowed; OWNER allowed "
                "unlimited unlocks within 24h of slot.end_at."
            ),
        )

    try:
        review = await unlock_review(
            db, review_id=review.id, admin=current_user
        )
    except ReviewImmutableError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contact = (
        await db.execute(select(Contact).where(Contact.id == booking.contact_id))
    ).scalar_one()
    return _to_response(review, contact)
