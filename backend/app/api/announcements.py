from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.core.logging import get_logger
from app.models.announcement import Announcement, AnnouncementStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.contact_preferred_type import ContactPreferredType
from app.models.booking import Booking
from app.models.tenant import Tenant
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementListResponse,
    AnnouncementResponse,
)
from app.services.sms import send_sms

logger = get_logger("announcements")

router = APIRouter(prefix="/api/v1/announcements", tags=["announcements"])


async def _get_recipient_phones(
    db: AsyncSession, tenant_id, filter_type_ids: list | None
) -> list[str]:
    """Get phone numbers of opted-in, active contacts, optionally filtered by appointment type."""
    query = (
        select(Contact.phone)
        .join(ContactConsent, ContactConsent.contact_id == Contact.id)
        .where(
            Contact.tenant_id == tenant_id,
            Contact.status == ContactStatus.ACTIVE,
            ContactConsent.status == ConsentStatus.OPTED_IN,
        )
    )

    if filter_type_ids:
        # Contacts who have preferred types matching OR have bookings with those types
        pref_contacts = select(ContactPreferredType.contact_id).where(
            ContactPreferredType.tenant_id == tenant_id,
            ContactPreferredType.appointment_type_id.in_(filter_type_ids),
        )
        booking_contacts = select(Booking.contact_id).where(
            Booking.tenant_id == tenant_id,
            Booking.appointment_type_id.in_(filter_type_ids),
        )
        query = query.where(
            Contact.id.in_(pref_contacts.union(booking_contacts))
        )

    result = await db.execute(query.distinct())
    return list(result.scalars().all())


async def _send_announcement(announcement_id: str, tenant_id: str):
    """Background task to send announcement SMS to recipients."""
    async with async_session_factory() as db:
        ann = await db.get(Announcement, announcement_id)
        if not ann:
            return
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            return

        ann.status = AnnouncementStatus.SENDING
        await db.flush()

        phones = await _get_recipient_phones(db, tenant_id, ann.filter_appointment_type_ids)
        ann.total_recipients = len(phones)
        await db.flush()

        sent = 0
        failed = 0
        for phone in phones:
            try:
                result = await send_sms(phone, ann.message, tenant)
                if result:
                    sent += 1
                else:
                    failed += 1
            except Exception:
                logger.exception(f"Failed to send announcement to {phone}")
                failed += 1

        ann.sent_count = sent
        ann.failed_count = failed
        ann.sent_at = datetime.now(timezone.utc)
        ann.status = AnnouncementStatus.SENT if failed == 0 else AnnouncementStatus.FAILED
        await db.commit()


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    body: AnnouncementCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    filter_ids = [str(tid) for tid in body.filter_appointment_type_ids] if body.filter_appointment_type_ids else None

    if body.scheduled_at:
        ann_status = AnnouncementStatus.SCHEDULED
    else:
        ann_status = AnnouncementStatus.DRAFT

    announcement = Announcement(
        tenant_id=tenant.id,
        message=body.message,
        filter_appointment_type_ids=filter_ids,
        scheduled_at=body.scheduled_at,
        status=ann_status,
        created_by_admin_id=current_user.id,
    )
    db.add(announcement)
    await db.flush()
    await db.refresh(announcement)

    if not body.scheduled_at:
        background_tasks.add_task(_send_announcement, str(announcement.id), str(tenant.id))

    return announcement


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    base = select(Announcement).where(Announcement.tenant_id == tenant.id)
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = base.order_by(Announcement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return AnnouncementListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    result = await db.execute(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.tenant_id == tenant.id,
        )
    )
    announcement = result.scalar_one_or_none()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return announcement


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_announcement(
    announcement_id: str,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    result = await db.execute(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.tenant_id == tenant.id,
        )
    )
    announcement = result.scalar_one_or_none()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if announcement.status != AnnouncementStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Only scheduled announcements can be cancelled")
    await db.delete(announcement)
    await db.flush()
