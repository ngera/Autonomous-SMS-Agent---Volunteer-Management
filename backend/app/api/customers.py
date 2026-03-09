import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.core.dependencies import CurrentUser, DbSession, ManagerUser
from app.models.booking import Booking
from app.models.contact import Contact
from app.models.contact_consent import (
    ContactConsent,
    ContactConsentHistory,
    ConsentStatus,
    OptInMethod,
    OptOutMethod,
)
from app.models.conversation import Conversation
from app.models.pattern import CustomerAppointmentPattern
from app.schemas.customer import (
    ConsentHistoryResponse,
    CsvImportResponse,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    OptOutRequest,
    PatternOverrideRequest,
    PatternResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
):
    query = select(Contact).options(joinedload(Contact.consent))

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Contact.phone.ilike(search_filter))
            | (Contact.name.ilike(search_filter))
            | (Contact.email.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    contacts = result.unique().scalars().all()

    items = []
    for contact in contacts:
        item = CustomerResponse(
            phone=contact.phone,
            name=contact.name,
            email=contact.email,
            status=contact.status,
            reminder_preference_days=contact.reminder_preference_days,
            consent_status=contact.consent.status if contact.consent else None,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )
        items.append(item)

    return CustomerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{phone}", response_model=CustomerResponse)
async def get_customer(phone: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Contact).options(joinedload(Contact.consent)).where(Contact.phone == phone)
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        phone=contact.phone,
        name=contact.name,
        email=contact.email,
        status=contact.status,
        reminder_preference_days=contact.reminder_preference_days,
        consent_status=contact.consent.status if contact.consent else None,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.put("/{phone}", response_model=CustomerResponse)
async def update_customer(
    phone: str, body: CustomerUpdate, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(Contact).options(joinedload(Contact.consent)).where(Contact.phone == phone)
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    await db.flush()
    await db.refresh(contact)

    return CustomerResponse(
        phone=contact.phone,
        name=contact.name,
        email=contact.email,
        status=contact.status,
        reminder_preference_days=contact.reminder_preference_days,
        consent_status=contact.consent.status if contact.consent else None,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.post("/import", response_model=CsvImportResponse)
async def import_customers_csv(
    file: UploadFile, db: DbSession, current_user: ManagerUser
):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        phone = row.get("phone", "").strip()
        if not phone:
            errors.append(f"Row {i}: missing phone number")
            continue

        # Check if contact already exists
        existing = await db.execute(
            select(Contact).where(Contact.phone == phone)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        contact = Contact(
            phone=phone,
            name=row.get("name", "").strip() or None,
            email=row.get("email", "").strip() or None,
        )
        db.add(contact)

        consent = ContactConsent(
            contact_phone=phone,
            status=ConsentStatus.UNCONTACTED,
        )
        db.add(consent)
        imported += 1

    await db.flush()
    return CsvImportResponse(imported=imported, skipped=skipped, errors=errors)


@router.get("/{phone}/bookings")
async def get_customer_bookings(phone: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Booking)
        .where(Booking.contact_phone == phone)
        .order_by(Booking.scheduled_at.desc())
    )
    return result.scalars().all()


@router.get("/{phone}/conversations")
async def get_customer_conversations(phone: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.contact_phone == phone)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{phone}/pattern", response_model=list[PatternResponse])
async def get_customer_pattern(phone: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(CustomerAppointmentPattern)
        .where(CustomerAppointmentPattern.contact_phone == phone)
    )
    return result.scalars().all()


@router.put("/{phone}/pattern/override", response_model=PatternResponse)
async def set_pattern_override(
    phone: str, body: PatternOverrideRequest, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(CustomerAppointmentPattern)
        .where(CustomerAppointmentPattern.contact_phone == phone)
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="No pattern found for this customer")

    pattern.manual_override_days = body.manual_override_days
    await db.flush()
    await db.refresh(pattern)
    return pattern


@router.delete("/{phone}/pattern/override", status_code=status.HTTP_204_NO_CONTENT)
async def clear_pattern_override(
    phone: str, db: DbSession, current_user: ManagerUser
):
    result = await db.execute(
        select(CustomerAppointmentPattern)
        .where(CustomerAppointmentPattern.contact_phone == phone)
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="No pattern found for this customer")

    pattern.manual_override_days = None
    await db.flush()


@router.post("/{phone}/optin-outreach", status_code=status.HTTP_202_ACCEPTED)
async def send_optin_outreach(
    phone: str, db: DbSession, current_user: ManagerUser
):
    """Send opt-in SMS to a customer. Full SMS integration in Phase 5."""
    result = await db.execute(select(Contact).where(Contact.phone == phone))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Update consent status to pending
    consent_result = await db.execute(
        select(ContactConsent).where(ContactConsent.contact_phone == phone)
    )
    consent = consent_result.scalar_one_or_none()
    if consent:
        old_status = consent.status
        consent.status = ConsentStatus.PENDING
        consent.last_status_change_at = datetime.now(timezone.utc)
    else:
        old_status = None
        consent = ContactConsent(
            contact_phone=phone,
            status=ConsentStatus.PENDING,
        )
        db.add(consent)

    # Record history
    history = ContactConsentHistory(
        contact_phone=phone,
        previous_status=old_status or ConsentStatus.UNCONTACTED,
        new_status=ConsentStatus.PENDING,
        changed_at=datetime.now(timezone.utc),
        changed_by_admin_id=current_user.id,
        reason="Admin-initiated opt-in outreach",
    )
    db.add(history)
    await db.flush()

    # TODO: Send actual SMS via Twilio in Phase 5
    return {"message": "Opt-in outreach initiated"}


@router.post("/{phone}/optout", status_code=status.HTTP_200_OK)
async def manual_optout(
    phone: str, body: OptOutRequest, db: DbSession, current_user: ManagerUser
):
    consent_result = await db.execute(
        select(ContactConsent).where(ContactConsent.contact_phone == phone)
    )
    consent = consent_result.scalar_one_or_none()
    if not consent:
        raise HTTPException(status_code=404, detail="Customer consent record not found")

    old_status = consent.status
    consent.status = ConsentStatus.OPTED_OUT
    consent.opted_out_at = datetime.now(timezone.utc)
    consent.opt_out_method = OptOutMethod.ADMIN_MANUAL
    consent.last_status_change_at = datetime.now(timezone.utc)

    history = ContactConsentHistory(
        contact_phone=phone,
        previous_status=old_status,
        new_status=ConsentStatus.OPTED_OUT,
        changed_at=datetime.now(timezone.utc),
        changed_by_admin_id=current_user.id,
        reason=body.reason,
    )
    db.add(history)
    await db.flush()

    return {"message": "Customer opted out successfully"}
