from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.core.logging import get_logger
from app.models.announcement import Announcement, AnnouncementStatus, RecipientScope
from app.models.contact import Contact, ContactStatus
from app.models.contact_consent import ContactConsent, ConsentStatus
from app.models.contact_preferred_type import ContactPreferredType
from app.models.booking import Booking, BookingStatus
from app.models.tenant import Tenant
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementListResponse,
    AnnouncementResponse,
)
from app.prompts.conversation import get_announcement_header_template
from app.services.sms import send_sms

logger = get_logger("announcements")


def _render_announcement_message(template: str, event_context: dict | None, body: str) -> str:
    """Prepend a rendered header to the body when event_context is present.

    Missing template placeholders render as empty strings. event_location_part is a
    convenience computed field that adds " at {event_location}" only when location exists.
    """
    if not event_context:
        return body

    class _Defaulting(dict):
        def __missing__(self, key: str) -> str:
            return ""

    ctx = _Defaulting(event_context)
    loc = ctx.get("event_location") or ""
    ctx["event_location_part"] = f" · {loc}" if loc else ""
    try:
        header = template.format_map(ctx)
    except (ValueError, KeyError, IndexError):
        # If the operator's template has bad placeholders, fall back to no header
        # rather than failing the send.
        header = ""
    return f"{header}{body}"

router = APIRouter(prefix="/api/v1/announcements", tags=["announcements"])


async def _get_recipient_phones(
    db: AsyncSession,
    tenant_id,
    filter_type_ids: list | None,
    recipient_scope: str = RecipientScope.ALL.value,
    event_context: dict | None = None,
) -> list[str]:
    """Get phone numbers of opted-in, active contacts.

    When recipient_scope == 'event_signups' and event_context has a date, restrict to
    contacts who already have a SCHEDULED/RESCHEDULED booking on that date for the
    targeted services. Otherwise the (filter_type_ids) broadens to anyone preferring
    those services or who has ever booked them.
    """
    query = (
        select(Contact.phone)
        .join(ContactConsent, ContactConsent.contact_id == Contact.id)
        .where(
            Contact.tenant_id == tenant_id,
            Contact.status == ContactStatus.ACTIVE,
            ContactConsent.status == ConsentStatus.OPTED_IN,
        )
    )

    if recipient_scope == RecipientScope.EVENT_SIGNUPS.value and event_context:
        from datetime import date as _date
        event_date_str = event_context.get("event_date")
        if not event_date_str:
            # No event date — fail closed: empty recipients rather than spamming everyone.
            return []
        try:
            event_date = _date.fromisoformat(event_date_str)
        except (ValueError, TypeError):
            return []
        booking_q = select(Booking.contact_id).where(
            Booking.tenant_id == tenant_id,
            func.date(Booking.scheduled_at) == event_date,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
        if filter_type_ids:
            booking_q = booking_q.where(Booking.appointment_type_id.in_(filter_type_ids))
        query = query.where(Contact.id.in_(booking_q))
    elif filter_type_ids:
        # Default: include contacts who have preferred types matching OR have bookings with those types
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


async def _append_announcement_to_history(
    db: AsyncSession,
    tenant_id,
    phone: str,
    body: str,
    ts: datetime,
) -> None:
    """Append the outgoing announcement to the recipient's active conversation.

    Creates a conversation row if one doesn't exist yet. Without this, real
    sends never show up in the volunteer's conversation log or on the
    Multi-Volunteer Test page (which seeds itself from message_history).
    """
    from app.models.conversation import Conversation, ConversationStatus

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.contact_phone == phone,
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.sender_type == "customer",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    convo = result.scalar_one_or_none()
    if not convo:
        contact_q = await db.execute(
            select(Contact).where(
                Contact.tenant_id == tenant_id,
                Contact.phone == phone,
            )
        )
        contact_row = contact_q.scalar_one_or_none()
        if contact_row is None:
            # No contact at all — nothing to attach history to.
            return
        convo = Conversation(
            tenant_id=tenant_id,
            contact_phone=phone,
            contact_id=contact_row.id,
            sender_type="customer",
            message_history=[],
            status=ConversationStatus.ACTIVE,
            current_step="greeting",
            last_message_at=ts,
        )
        db.add(convo)
        await db.flush()

    from app.modules.conversation import trim_message_history
    history = list(convo.message_history or [])
    history.append({
        "role": "assistant",
        "content": body,
        "timestamp": ts.isoformat(),
        "kind": "announcement",
    })
    convo.message_history = trim_message_history(history)
    convo.last_message_at = ts


async def _send_announcement(announcement_id: str, tenant_id: str):
    """Background task to send announcement SMS to recipients."""
    async with async_session_factory() as db:
        ann = await db.get(Announcement, announcement_id)
        if not ann:
            return
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            return

        # Persist the in-progress state immediately so a later exception in
        # this function doesn't roll the row back to DRAFT.
        ann.status = AnnouncementStatus.SENDING
        await db.commit()

        phones = await _get_recipient_phones(
            db,
            tenant_id,
            ann.filter_appointment_type_ids,
            recipient_scope=ann.recipient_scope or RecipientScope.ALL.value,
            event_context=ann.event_context,
        )
        ann.total_recipients = len(phones)
        await db.flush()

        # Build the final outgoing message: prepend rendered event header when applicable.
        if ann.event_context:
            template = await get_announcement_header_template(db, tenant.id)
            outgoing = _render_announcement_message(template, ann.event_context, ann.message)
        else:
            outgoing = ann.message

        sent = 0
        failed = 0
        for phone in phones:
            sent_ok = False
            try:
                result = await send_sms(phone, outgoing, tenant)
                if result:
                    sent += 1
                    sent_ok = True
                else:
                    failed += 1
            except Exception:
                logger.exception(f"Failed to send announcement to {phone}")
                failed += 1

            if sent_ok:
                try:
                    await _append_announcement_to_history(
                        db, tenant_id, phone, outgoing, datetime.now(timezone.utc)
                    )
                except Exception:
                    logger.exception(
                        f"Failed to append announcement to conversation history for {phone}"
                    )

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
        # There's no "save draft" path; an immediate send is queued for the
        # background task. Start at SENDING so the UI's instant refetch shows
        # the correct intent (instead of misleading "DRAFT").
        ann_status = AnnouncementStatus.SENDING

    announcement = Announcement(
        tenant_id=tenant.id,
        message=body.message,
        filter_appointment_type_ids=filter_ids,
        scheduled_at=body.scheduled_at,
        status=ann_status,
        event_context=body.event_context.model_dump() if body.event_context else None,
        recipient_scope=body.recipient_scope.value,
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
