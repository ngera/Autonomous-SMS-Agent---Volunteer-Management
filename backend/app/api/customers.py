import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.contact_preferred_type import ContactPreferredType
from app.models.contact_consent import (
    ContactConsent,
    ContactConsentHistory,
    ConsentStatus,
    OptOutMethod,
)
from app.models.conversation import Conversation
from app.models.pattern import CustomerAppointmentPattern
from app.schemas.customer import (
    ConsentHistoryResponse,
    CsvImportResponse,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    OptOutRequest,
    PatternOverrideRequest,
    PatternResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


async def _get_preferred_type_ids(db: DbSession, contact_id, tenant_id) -> list:
    result = await db.execute(
        select(ContactPreferredType.appointment_type_id).where(
            ContactPreferredType.contact_id == contact_id,
            ContactPreferredType.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


async def _sync_preferred_types(db, contact_id, tenant_id, type_ids: list):
    await db.execute(
        select(ContactPreferredType).where(
            ContactPreferredType.contact_id == contact_id,
            ContactPreferredType.tenant_id == tenant_id,
        )
    )
    from sqlalchemy import delete
    await db.execute(
        delete(ContactPreferredType).where(
            ContactPreferredType.contact_id == contact_id,
            ContactPreferredType.tenant_id == tenant_id,
        )
    )
    for type_id in type_ids:
        db.add(ContactPreferredType(
            tenant_id=tenant_id,
            contact_id=contact_id,
            appointment_type_id=type_id,
        ))
    await db.flush()


def _build_customer_response(contact, consent_status, preferred_type_ids=None):
    return CustomerResponse(
        phone=contact.phone,
        name=contact.name,
        email=contact.email,
        sex=contact.sex,
        status=contact.status,
        reminder_preference_days=contact.reminder_preference_days,
        consent_status=consent_status,
        preferred_appointment_type_ids=preferred_type_ids or [],
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
):
    query = select(Contact).options(joinedload(Contact.consent)).where(
        Contact.tenant_id == tenant.id
    )

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Contact.phone.ilike(search_filter))
            | (Contact.name.ilike(search_filter))
            | (Contact.email.ilike(search_filter))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    contacts = result.unique().scalars().all()

    items = []
    for contact in contacts:
        pref_ids = await _get_preferred_type_ids(db, contact.id, tenant.id)
        item = _build_customer_response(
            contact,
            contact.consent.status if contact.consent else None,
            pref_ids,
        )
        items.append(item)

    return CustomerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{phone}", response_model=CustomerResponse)
async def get_customer(phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(Contact).options(joinedload(Contact.consent)).where(
            Contact.phone == phone, Contact.tenant_id == tenant.id
        )
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    pref_ids = await _get_preferred_type_ids(db, contact.id, tenant.id)
    return _build_customer_response(
        contact,
        contact.consent.status if contact.consent else None,
        pref_ids,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    existing = await db.execute(
        select(Contact).where(Contact.phone == body.phone, Contact.tenant_id == tenant.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer with this phone already exists")

    contact = Contact(
        tenant_id=tenant.id,
        phone=body.phone,
        name=body.name,
        email=body.email,
        sex=body.sex,
        reminder_preference_days=body.reminder_preference_days,
    )
    db.add(contact)
    await db.flush()

    consent = ContactConsent(
        tenant_id=tenant.id,
        contact_id=contact.id,
        contact_phone=body.phone,
        status=ConsentStatus.UNCONTACTED,
    )
    db.add(consent)

    if body.preferred_appointment_type_ids:
        await _sync_preferred_types(db, contact.id, tenant.id, body.preferred_appointment_type_ids)

    await db.flush()
    await db.refresh(contact)

    return _build_customer_response(
        contact,
        ConsentStatus.UNCONTACTED,
        body.preferred_appointment_type_ids,
    )


@router.delete("/{phone}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(phone: str, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant):
    result = await db.execute(
        select(Contact).where(Contact.phone == phone, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    active_count = await db.execute(
        select(func.count()).select_from(Booking).where(
            Booking.contact_id == contact.id,
            Booking.tenant_id == tenant.id,
            Booking.status.in_([BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]),
        )
    )
    if (active_count.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete customer with active bookings")

    await db.delete(contact)
    await db.flush()


@router.put("/{phone}", response_model=CustomerResponse)
async def update_customer(
    phone: str, body: CustomerUpdate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Contact).options(joinedload(Contact.consent)).where(
            Contact.phone == phone, Contact.tenant_id == tenant.id
        )
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = body.model_dump(exclude_unset=True)
    pref_ids = update_data.pop("preferred_appointment_type_ids", None)

    for field, value in update_data.items():
        setattr(contact, field, value)

    if pref_ids is not None:
        await _sync_preferred_types(db, contact.id, tenant.id, pref_ids)

    await db.flush()
    await db.refresh(contact)

    current_pref_ids = await _get_preferred_type_ids(db, contact.id, tenant.id)
    return _build_customer_response(
        contact,
        contact.consent.status if contact.consent else None,
        current_pref_ids,
    )


@router.post("/import", response_model=CsvImportResponse)
async def import_customers_csv(
    file: UploadFile, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
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

        existing = await db.execute(
            select(Contact).where(Contact.phone == phone, Contact.tenant_id == tenant.id)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        contact = Contact(
            tenant_id=tenant.id,
            phone=phone,
            name=row.get("name", "").strip() or None,
            email=row.get("email", "").strip() or None,
        )
        db.add(contact)
        await db.flush()

        consent = ContactConsent(
            tenant_id=tenant.id,
            contact_id=contact.id,
            contact_phone=phone,
            status=ConsentStatus.UNCONTACTED,
        )
        db.add(consent)
        imported += 1

    await db.flush()
    return CsvImportResponse(imported=imported, skipped=skipped, errors=errors)


@router.get("/{phone}/bookings")
async def get_customer_bookings(
    phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Booking)
        .where(Booking.contact_phone == phone, Booking.tenant_id == tenant.id)
        .order_by(Booking.scheduled_at.desc())
    )
    return result.scalars().all()


@router.get("/{phone}/conversations")
async def get_customer_conversations(
    phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.contact_phone == phone, Conversation.tenant_id == tenant.id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{phone}/pattern", response_model=list[PatternResponse])
async def get_customer_pattern(
    phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(CustomerAppointmentPattern).where(
            CustomerAppointmentPattern.contact_phone == phone,
            CustomerAppointmentPattern.tenant_id == tenant.id,
        )
    )
    return result.scalars().all()


@router.put("/{phone}/pattern/override", response_model=PatternResponse)
async def set_pattern_override(
    phone: str, body: PatternOverrideRequest, db: DbSession, current_user: ManagerUser,
    tenant: CurrentTenant
):
    result = await db.execute(
        select(CustomerAppointmentPattern).where(
            CustomerAppointmentPattern.contact_phone == phone,
            CustomerAppointmentPattern.tenant_id == tenant.id,
        )
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
    phone: str, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(CustomerAppointmentPattern).where(
            CustomerAppointmentPattern.contact_phone == phone,
            CustomerAppointmentPattern.tenant_id == tenant.id,
        )
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="No pattern found for this customer")

    pattern.manual_override_days = None
    await db.flush()


@router.post("/{phone}/optin-outreach", status_code=status.HTTP_202_ACCEPTED)
async def send_optin_outreach(
    phone: str, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(Contact).where(Contact.phone == phone, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    consent_result = await db.execute(
        select(ContactConsent).where(
            ContactConsent.contact_id == contact.id,
            ContactConsent.tenant_id == tenant.id,
        )
    )
    consent = consent_result.scalar_one_or_none()
    if consent:
        old_status = consent.status
        consent.status = ConsentStatus.PENDING
        consent.last_status_change_at = datetime.now(timezone.utc)
    else:
        old_status = None
        consent = ContactConsent(
            tenant_id=tenant.id,
            contact_id=contact.id,
            contact_phone=phone,
            status=ConsentStatus.PENDING,
        )
        db.add(consent)

    history = ContactConsentHistory(
        tenant_id=tenant.id,
        contact_id=contact.id,
        contact_phone=phone,
        previous_status=old_status or ConsentStatus.UNCONTACTED,
        new_status=ConsentStatus.PENDING,
        changed_at=datetime.now(timezone.utc),
        changed_by_admin_id=current_user.id,
        reason="Admin-initiated opt-in outreach",
    )
    db.add(history)
    await db.flush()

    return {"message": "Opt-in outreach initiated"}


@router.post("/{phone}/optout", status_code=status.HTTP_200_OK)
async def manual_optout(
    phone: str, body: OptOutRequest, db: DbSession, current_user: ManagerUser,
    tenant: CurrentTenant
):
    # Find contact first
    contact_result = await db.execute(
        select(Contact).where(Contact.phone == phone, Contact.tenant_id == tenant.id)
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    consent_result = await db.execute(
        select(ContactConsent).where(
            ContactConsent.contact_id == contact.id,
            ContactConsent.tenant_id == tenant.id,
        )
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
        tenant_id=tenant.id,
        contact_id=contact.id,
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
