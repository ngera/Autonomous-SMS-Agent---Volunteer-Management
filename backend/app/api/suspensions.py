import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.dependencies import CurrentUser, DbSession, ManagerUser, OwnerUser
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.suspension import ContactSuspension, ReviewDecision, SuspensionType
from app.schemas.suspension import (
    ManualSuspendRequest,
    ReviewRequest,
    SuspensionListResponse,
    SuspensionResponse,
)

router = APIRouter(prefix="/api/v1/suspensions", tags=["suspensions"])


async def _enrich_suspension(db: DbSession, suspension: ContactSuspension) -> SuspensionResponse:
    """Add contact_name to a suspension response."""
    contact_result = await db.execute(
        select(Contact.name).where(Contact.phone == suspension.contact_phone)
    )
    contact_name = contact_result.scalar_one_or_none()
    return SuspensionResponse(
        id=suspension.id,
        contact_phone=suspension.contact_phone,
        contact_name=contact_name,
        suspended_at=suspension.suspended_at,
        suspension_type=suspension.suspension_type,
        reason=suspension.reason,
        strike_ids=suspension.strike_ids,
        conversation_id=suspension.conversation_id,
        notification_sent_at=suspension.notification_sent_at,
        reviewed_by_admin_id=suspension.reviewed_by_admin_id,
        reviewed_at=suspension.reviewed_at,
        review_decision=suspension.review_decision,
        review_notes=suspension.review_notes,
        lifted_at=suspension.lifted_at,
    )


@router.get("", response_model=SuspensionListResponse)
async def list_suspensions(db: DbSession, current_user: CurrentUser):
    # Unreviewed first, then by date
    query = select(ContactSuspension).order_by(
        ContactSuspension.reviewed_at.is_(None).desc(),
        ContactSuspension.suspended_at.desc(),
    )
    result = await db.execute(query)
    suspensions = result.scalars().all()
    items = [await _enrich_suspension(db, s) for s in suspensions]
    return SuspensionListResponse(items=items, total=len(items))


@router.get("/{suspension_id}", response_model=SuspensionResponse)
async def get_suspension(
    suspension_id: uuid.UUID, db: DbSession, current_user: CurrentUser
):
    result = await db.execute(
        select(ContactSuspension).where(ContactSuspension.id == suspension_id)
    )
    suspension = result.scalar_one_or_none()
    if not suspension:
        raise HTTPException(status_code=404, detail="Suspension not found")
    return await _enrich_suspension(db, suspension)


@router.post("/{suspension_id}/lift", response_model=SuspensionResponse)
async def lift_suspension(
    suspension_id: uuid.UUID,
    body: ReviewRequest,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(
        select(ContactSuspension).where(ContactSuspension.id == suspension_id)
    )
    suspension = result.scalar_one_or_none()
    if not suspension:
        raise HTTPException(status_code=404, detail="Suspension not found")

    now = datetime.now(timezone.utc)
    suspension.review_decision = ReviewDecision.LIFTED
    suspension.reviewed_by_admin_id = current_user.id
    suspension.reviewed_at = now
    suspension.review_notes = body.notes
    suspension.lifted_at = now

    # Restore contact status
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == suspension.contact_phone)
    )
    contact = contact_result.scalar_one_or_none()
    if contact:
        contact.status = ContactStatus.ACTIVE

    # Restore consent
    consent_result = await db.execute(
        select(ContactConsent).where(
            ContactConsent.contact_phone == suspension.contact_phone
        )
    )
    consent = consent_result.scalar_one_or_none()
    if consent and consent.status == ConsentStatus.BLOCKED:
        consent.status = ConsentStatus.OPTED_IN
        consent.last_status_change_at = now

    await db.flush()
    await db.refresh(suspension)
    return await _enrich_suspension(db, suspension)


@router.post("/{suspension_id}/confirm", response_model=SuspensionResponse)
async def confirm_suspension(
    suspension_id: uuid.UUID,
    body: ReviewRequest,
    db: DbSession,
    current_user: ManagerUser,
):
    result = await db.execute(
        select(ContactSuspension).where(ContactSuspension.id == suspension_id)
    )
    suspension = result.scalar_one_or_none()
    if not suspension:
        raise HTTPException(status_code=404, detail="Suspension not found")

    suspension.review_decision = ReviewDecision.CONFIRMED
    suspension.reviewed_by_admin_id = current_user.id
    suspension.reviewed_at = datetime.now(timezone.utc)
    suspension.review_notes = body.notes

    await db.flush()
    await db.refresh(suspension)
    return await _enrich_suspension(db, suspension)


@router.post("/{suspension_id}/ban", response_model=SuspensionResponse)
async def ban_user(
    suspension_id: uuid.UUID,
    body: ReviewRequest,
    db: DbSession,
    current_user: OwnerUser,
):
    result = await db.execute(
        select(ContactSuspension).where(ContactSuspension.id == suspension_id)
    )
    suspension = result.scalar_one_or_none()
    if not suspension:
        raise HTTPException(status_code=404, detail="Suspension not found")

    now = datetime.now(timezone.utc)
    suspension.review_decision = ReviewDecision.BANNED
    suspension.reviewed_by_admin_id = current_user.id
    suspension.reviewed_at = now
    suspension.review_notes = body.notes

    # Set contact to banned
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == suspension.contact_phone)
    )
    contact = contact_result.scalar_one_or_none()
    if contact:
        contact.status = ContactStatus.BANNED

    await db.flush()
    await db.refresh(suspension)
    return await _enrich_suspension(db, suspension)


@router.post("/customers/{phone}/suspend", response_model=SuspensionResponse, status_code=status.HTTP_201_CREATED)
async def manual_suspend(
    phone: str, body: ManualSuspendRequest, db: DbSession, current_user: ManagerUser
):
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == phone)
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    now = datetime.now(timezone.utc)
    contact.status = ContactStatus.SUSPENDED

    suspension = ContactSuspension(
        contact_phone=phone,
        suspension_type=SuspensionType.MANUAL,
        reason=body.reason,
        notification_sent_at=now,
    )
    db.add(suspension)

    # Update consent
    consent_result = await db.execute(
        select(ContactConsent).where(ContactConsent.contact_phone == phone)
    )
    consent = consent_result.scalar_one_or_none()
    if consent:
        consent.status = ConsentStatus.BLOCKED
        consent.last_status_change_at = now

    await db.flush()
    await db.refresh(suspension)
    return await _enrich_suspension(db, suspension)
