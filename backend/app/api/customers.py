import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser

logger = logging.getLogger(__name__)
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact, ContactSex, ContactStatus
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
    VolunteerHoursSummary,
    VolunteerServiceStat,
    VolunteerStatsResponse,
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


_BOOL_TRUE = {"yes", "y", "true", "1"}
_BOOL_FALSE = {"no", "n", "false", "0", ""}
_DOW_NAMES = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
_VALID_AVAILABILITY = {
    "weekday_am", "weekday_pm", "weekday_eve",
    "weekend_am", "weekend_pm", "weekend_eve",
}


def _parse_bool_or_none(s: str | None) -> bool | None:
    if s is None:
        return None
    v = s.strip().lower()
    if v == "":
        return None
    if v in _BOOL_TRUE:
        return True
    if v in _BOOL_FALSE - {""}:
        return False
    raise ValueError(f"invalid yes/no value: {s!r}")


def _parse_time_str(t: str) -> str:
    """Accept 'HH:MM' or 'HH:MM:SS' and return 'HH:MM:SS'."""
    t = t.strip()
    if len(t) == 5:
        t = f"{t}:00"
    # Quick sanity check
    parts = t.split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"invalid time {t!r}")
    return t


def _parse_weekly_hours(s: str) -> list[dict]:
    """Parse 'Mon 09:00-12:00; Wed 13:00-15:00' into JSONB blocks."""
    s = (s or "").strip()
    if not s:
        return []
    blocks: list[dict] = []
    for raw in s.split(";"):
        piece = raw.strip()
        if not piece:
            continue
        try:
            day_part, time_part = piece.split(" ", 1)
            start_raw, end_raw = time_part.split("-", 1)
            dow = _DOW_NAMES[day_part.strip().lower()]
            blocks.append({
                "day_of_week": dow,
                "start_time": _parse_time_str(start_raw),
                "end_time": _parse_time_str(end_raw),
            })
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid weekly_hours block: {piece!r}") from exc
    return blocks


def _parse_availability(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    out: list[str] = []
    for raw in s.split(";"):
        v = raw.strip().lower()
        if not v:
            continue
        if v not in _VALID_AVAILABILITY:
            raise ValueError(f"invalid availability slot: {v!r}")
        if v not in out:
            out.append(v)
    return out


def _parse_unavailable_dates(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    out: list[str] = []
    for raw in s.split(";"):
        v = raw.strip()
        if not v:
            continue
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"invalid date {v!r} (expected YYYY-MM-DD)") from exc
        out.append(v)
    return out


def _parse_services(s: str, name_to_id: dict[str, "uuid.UUID"]) -> list:
    s = (s or "").strip()
    if not s or s.upper() == "ALL":
        return []
    ids = []
    for raw in s.split(";"):
        name = raw.strip()
        if not name:
            continue
        tid = name_to_id.get(name.lower())
        if tid is None:
            raise ValueError(f"unknown service {name!r}")
        ids.append(tid)
    return ids


def _build_customer_response(
    contact,
    consent_status,
    preferred_type_ids=None,
    total_minutes: int = 0,
    roster_visibility_history=None,
):
    return CustomerResponse(
        id=contact.id,
        phone=contact.phone,
        name=contact.name,
        email=contact.email,
        sex=contact.sex,
        status=contact.status,
        all_services_enabled=contact.all_services_enabled,
        background_check_required=contact.background_check_required,
        availability=contact.availability or [],
        weekly_hours=contact.weekly_hours or [],
        unavailable_dates=contact.unavailable_dates or [],
        total_minutes=total_minutes,
        reminder_preference_days=contact.reminder_preference_days,
        consent_status=consent_status,
        preferred_appointment_type_ids=preferred_type_ids or [],
        preferences=contact.preferences,
        notes=contact.notes,
        memory_updated_at=contact.memory_updated_at,
        default_roster_visibility=contact.default_roster_visibility,
        roster_visibility_history=roster_visibility_history or [],
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
    status_filter: ContactStatus | None = Query(None, alias="status"),
    consent_filter: ConsentStatus | None = Query(None, alias="consent_status"),
    background_check_required: bool | None = None,
    availability: str | None = None,
    include_archived: bool = False,
):
    base = select(Contact).options(joinedload(Contact.consent)).where(
        Contact.tenant_id == tenant.id
    )
    if not include_archived:
        base = base.where(Contact.is_archived.is_(False))
    unfiltered_total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    query = base
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Contact.phone.ilike(search_filter))
            | (Contact.name.ilike(search_filter))
            | (Contact.email.ilike(search_filter))
        )
    if status_filter is not None:
        query = query.where(Contact.status == status_filter)
    if background_check_required is not None:
        query = query.where(Contact.background_check_required == background_check_required)
    if availability:
        query = query.where(Contact.availability.op("@>")([availability]))
    if consent_filter is not None:
        query = query.join(ContactConsent, ContactConsent.contact_id == Contact.id).where(
            ContactConsent.status == consent_filter
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Contact.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    contacts = result.unique().scalars().all()

    contact_ids = [c.id for c in contacts]
    hours_map: dict = {}
    if contact_ids:
        rows = await db.execute(
            select(
                Booking.contact_id,
                func.coalesce(
                    func.sum(AppointmentType.duration_minutes), 0
                ).label("minutes"),
            )
            .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
            .where(
                Booking.tenant_id == tenant.id,
                Booking.contact_id.in_(contact_ids),
                Booking.status == BookingStatus.COMPLETED,
            )
            .group_by(Booking.contact_id)
        )
        hours_map = {row[0]: int(row[1] or 0) for row in rows.all()}

    items = []
    for contact in contacts:
        pref_ids = await _get_preferred_type_ids(db, contact.id, tenant.id)
        item = _build_customer_response(
            contact,
            contact.consent.status if contact.consent else None,
            pref_ids,
            total_minutes=hours_map.get(contact.id, 0),
        )
        items.append(item)

    return CustomerListResponse(
        items=items,
        total=total,
        total_unfiltered=unfiltered_total,
        page=page,
        page_size=page_size,
    )


@router.get("/hours-summary", response_model=VolunteerHoursSummary)
async def get_volunteer_hours_summary(
    db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    """Sum of completed-booking durations across all volunteers.

    `last_month` is the previous calendar month. Falls back to scheduled_at when
    completed_at is null (older bookings before the column was always populated).
    """
    booking_when = func.coalesce(Booking.completed_at, Booking.scheduled_at)

    base_total = (await db.execute(
        select(func.coalesce(func.sum(AppointmentType.duration_minutes), 0))
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .where(
            Booking.tenant_id == tenant.id,
            Booking.status == BookingStatus.COMPLETED,
        )
    )).scalar() or 0

    today = date.today()
    if today.month == 1:
        lm_start = date(today.year - 1, 12, 1)
        lm_end = date(today.year, 1, 1)
    else:
        lm_start = date(today.year, today.month - 1, 1)
        lm_end = date(today.year, today.month, 1)
    lm_start_dt = datetime.combine(lm_start, datetime.min.time(), tzinfo=timezone.utc)
    lm_end_dt = datetime.combine(lm_end, datetime.min.time(), tzinfo=timezone.utc)

    last_month_total = (await db.execute(
        select(func.coalesce(func.sum(AppointmentType.duration_minutes), 0))
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .where(
            Booking.tenant_id == tenant.id,
            Booking.status == BookingStatus.COMPLETED,
            booking_when >= lm_start_dt,
            booking_when < lm_end_dt,
        )
    )).scalar() or 0

    return VolunteerHoursSummary(
        total_minutes_all_time=int(base_total),
        total_minutes_last_month=int(last_month_total),
    )


@router.get("/{phone}", response_model=CustomerResponse)
async def get_customer(phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    from app.models.contact_preference_history import (
        PREFERENCE_FIELD_ROSTER_VISIBILITY,
        ContactPreferenceHistory,
    )

    result = await db.execute(
        select(Contact).options(joinedload(Contact.consent)).where(
            Contact.phone == phone, Contact.tenant_id == tenant.id
        )
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Customer not found")

    pref_ids = await _get_preferred_type_ids(db, contact.id, tenant.id)

    # Roster-visibility change timeline (newest first).
    history_rows = (await db.execute(
        select(ContactPreferenceHistory).where(
            ContactPreferenceHistory.tenant_id == tenant.id,
            ContactPreferenceHistory.contact_id == contact.id,
            ContactPreferenceHistory.field == PREFERENCE_FIELD_ROSTER_VISIBILITY,
        ).order_by(ContactPreferenceHistory.changed_at.desc())
    )).scalars().all()
    history = [
        {
            "previous_value": r.previous_value,
            "new_value": r.new_value,
            "source": r.source,
            "source_booking_id": r.source_booking_id,
            "changed_at": r.changed_at,
        }
        for r in history_rows
    ]

    return _build_customer_response(
        contact,
        contact.consent.status if contact.consent else None,
        pref_ids,
        roster_visibility_history=history,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    logger.info("CREATE CUSTOMER request body: %s", body.model_dump())
    existing = await db.execute(
        select(Contact).where(Contact.phone == body.phone, Contact.tenant_id == tenant.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer with this phone already exists")

    try:
        contact = Contact(
            tenant_id=tenant.id,
            phone=body.phone,
            name=body.name,
            email=body.email,
            sex=body.sex,
            all_services_enabled=body.all_services_enabled,
            background_check_required=body.background_check_required,
            availability=body.availability or None,
            weekly_hours=[b.model_dump(mode="json") for b in body.weekly_hours] or None,
            unavailable_dates=[d.isoformat() for d in body.unavailable_dates] or None,
            reminder_preference_days=body.reminder_preference_days,
        )
        db.add(contact)
        await db.flush()
        logger.info("Contact created: id=%s, phone=%s", contact.id, contact.phone)

        consent = ContactConsent(
            tenant_id=tenant.id,
            contact_id=contact.id,
            contact_phone=body.phone,
            status=ConsentStatus.UNCONTACTED,
        )
        db.add(consent)
        logger.info("Consent created for contact %s", contact.id)

        if body.preferred_appointment_type_ids:
            logger.info("Syncing preferred types: %s", body.preferred_appointment_type_ids)
            await _sync_preferred_types(db, contact.id, tenant.id, body.preferred_appointment_type_ids)
            logger.info("Preferred types synced successfully")

        await db.flush()
        await db.refresh(contact)
        logger.info("Customer creation complete: %s", contact.id)
    except Exception as e:
        logger.error("Error creating customer: %s", e, exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create customer: {e}")

    return _build_customer_response(
        contact,
        ConsentStatus.UNCONTACTED,
        body.preferred_appointment_type_ids,
    )


@router.delete("/{phone}")
async def delete_customer(phone: str, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant):
    """Delete a volunteer.

    Hard-deletes the row only when there's nothing to preserve. If the
    volunteer has any bookings or conversations, archives them instead so the
    audit trail stays intact. Returns ``{"action": "deleted"|"archived"}`` so
    the UI can word the success message correctly.
    """
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

    booking_count = (await db.execute(
        select(func.count()).select_from(Booking).where(
            Booking.contact_id == contact.id, Booking.tenant_id == tenant.id,
        )
    )).scalar() or 0
    convo_count = (await db.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.contact_id == contact.id, Conversation.tenant_id == tenant.id,
        )
    )).scalar() or 0

    if booking_count > 0 or convo_count > 0:
        # Preserve history — archive the volunteer instead of removing the row.
        contact.is_archived = True
        await db.flush()
        return {"action": "archived", "booking_count": booking_count, "conversation_count": convo_count}

    # No history → safe to hard-delete. Most child tables don't have
    # ON DELETE CASCADE on their contact_id FK, so we clear them explicitly,
    # children-first, inside the request transaction.
    from sqlalchemy import delete as sql_delete
    from app.models.reminder import Reminder
    from app.models.strike import ContactStrike
    from app.models.suspension import ContactSuspension
    from app.models.token_usage import TokenUsage

    for model in (
        Reminder,
        ContactSuspension,
        TokenUsage,
        ContactConsentHistory,
        ContactConsent,
        ContactStrike,
        CustomerAppointmentPattern,
        ContactPreferredType,
    ):
        await db.execute(
            sql_delete(model).where(
                model.contact_id == contact.id,
                model.tenant_id == tenant.id,
            )
        )

    await db.delete(contact)
    await db.flush()
    return {"action": "deleted"}


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

    update_data = body.model_dump(mode="json", exclude_unset=True)
    pref_ids = update_data.pop("preferred_appointment_type_ids", None)
    new_phone = update_data.pop("phone", None)

    # Handle phone change
    if new_phone and new_phone != contact.phone:
        # Check uniqueness within tenant
        existing = await db.execute(
            select(Contact).where(
                Contact.phone == new_phone, Contact.tenant_id == tenant.id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"A customer with phone '{new_phone}' already exists for this tenant.",
            )
        old_phone = contact.phone
        contact.phone = new_phone
        # Update denormalized contact_phone on bookings and conversations
        from app.models.booking import Booking
        from app.models.conversation import Conversation
        await db.execute(
            Booking.__table__.update()
            .where(Booking.contact_id == contact.id)
            .values(contact_phone=new_phone)
        )
        await db.execute(
            Conversation.__table__.update()
            .where(Conversation.contact_id == contact.id)
            .values(contact_phone=new_phone)
        )

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
    # utf-8-sig strips the BOM that the frontend export prepends; without it
    # the first column header reads as "﻿phone" and every row fails.
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])

    # Build a tenant-scoped service-name → ID map once so the row loop can
    # resolve the semicolon-separated names from the export's `services` column.
    type_rows = await db.execute(
        select(AppointmentType.id, AppointmentType.name).where(
            AppointmentType.tenant_id == tenant.id,
        )
    )
    name_to_id: dict[str, "uuid.UUID"] = {
        n.strip().lower(): tid for tid, n in type_rows.all()
    }

    imported = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    # Track phones already processed in this file so the second occurrence
    # of the same phone is reported as a duplicate instead of silently
    # overwriting the first.
    seen_phones: set[str] = set()

    def _norm_name(s: str | None) -> str:
        return (s or "").strip().lower()

    for i, row in enumerate(reader, start=2):
        phone = (row.get("phone") or "").strip()
        if not phone:
            errors.append(f"Row {i}: missing phone number")
            skipped += 1
            continue

        if phone in seen_phones:
            errors.append(
                f"Row {i}: duplicate phone {phone} appears earlier in this file"
            )
            skipped += 1
            continue
        seen_phones.add(phone)

        # Parse every column that's present in the file. Missing columns are
        # left untouched on update (and default-empty on create).
        try:
            updates: dict = {}
            if "name" in fieldnames:
                updates["name"] = (row.get("name") or "").strip() or None
            if "email" in fieldnames:
                updates["email"] = (row.get("email") or "").strip() or None
            if "sex" in fieldnames:
                v = (row.get("sex") or "").strip().lower()
                updates["sex"] = ContactSex(v) if v else None
            if "status" in fieldnames:
                v = (row.get("status") or "").strip().lower()
                updates["status"] = ContactStatus(v) if v else ContactStatus.ACTIVE
            if "background_check_required" in fieldnames:
                bc = _parse_bool_or_none(row.get("background_check_required"))
                if bc is not None:
                    updates["background_check_required"] = bc
            if "all_services_enabled" in fieldnames:
                ase = _parse_bool_or_none(row.get("all_services_enabled"))
                if ase is not None:
                    updates["all_services_enabled"] = ase
            if "availability" in fieldnames:
                avail = _parse_availability(row.get("availability") or "")
                updates["availability"] = avail or None
            if "weekly_hours" in fieldnames:
                wh = _parse_weekly_hours(row.get("weekly_hours") or "")
                updates["weekly_hours"] = wh or None
            if "unavailable_dates" in fieldnames:
                ud = _parse_unavailable_dates(row.get("unavailable_dates") or "")
                updates["unavailable_dates"] = ud or None
            if "reminder_preference_days" in fieldnames:
                v = (row.get("reminder_preference_days") or "").strip()
                if v:
                    updates["reminder_preference_days"] = int(v)

            services_present = "services" in fieldnames
            service_ids: list = []
            if services_present:
                service_ids = _parse_services(row.get("services") or "", name_to_id)

            consent_value: ConsentStatus | None = None
            if "consent" in fieldnames:
                cv = (row.get("consent") or "").strip().lower()
                if cv:
                    consent_value = ConsentStatus(cv)
        except (ValueError, KeyError) as exc:
            errors.append(f"Row {i}: {exc}")
            skipped += 1
            continue

        existing = await db.execute(
            select(Contact).where(Contact.phone == phone, Contact.tenant_id == tenant.id)
        )
        contact = existing.scalar_one_or_none()

        # (phone, name) is the identity key for import. If a row's phone matches
        # an existing contact whose stored name differs from the row's name,
        # treat it as a different person and skip — never silently overwrite.
        if contact is not None and "name" in fieldnames:
            row_name = _norm_name(updates.get("name"))
            existing_name = _norm_name(contact.name)
            if row_name and existing_name and row_name != existing_name:
                errors.append(
                    f"Row {i}: phone {phone} already belongs to "
                    f"{contact.name!r}; refusing to overwrite with {updates['name']!r}"
                )
                skipped += 1
                continue

        if contact is None:
            contact = Contact(tenant_id=tenant.id, phone=phone, **updates)
            db.add(contact)
            await db.flush()

            db.add(ContactConsent(
                tenant_id=tenant.id,
                contact_id=contact.id,
                contact_phone=phone,
                status=consent_value or ConsentStatus.UNCONTACTED,
            ))

            if services_present and service_ids:
                for tid in service_ids:
                    db.add(ContactPreferredType(
                        tenant_id=tenant.id,
                        contact_id=contact.id,
                        appointment_type_id=tid,
                    ))
            imported += 1
        else:
            for field, value in updates.items():
                setattr(contact, field, value)
            if services_present:
                # Replace the preferred-types set so updates are deterministic.
                await _sync_preferred_types(db, contact.id, tenant.id, service_ids)
            await db.flush()
            updated += 1

    await db.flush()
    return CsvImportResponse(
        imported=imported, updated=updated, skipped=skipped, errors=errors
    )


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


@router.get("/{phone}/volunteer-stats", response_model=VolunteerStatsResponse)
async def get_customer_volunteer_stats(
    phone: str, db: DbSession, current_user: CurrentUser, tenant: CurrentTenant
):
    contact_result = await db.execute(
        select(Contact.id).where(
            Contact.phone == phone, Contact.tenant_id == tenant.id
        )
    )
    contact_id = contact_result.scalar_one_or_none()
    if not contact_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    rows = (await db.execute(
        select(
            AppointmentType.id,
            AppointmentType.name,
            AppointmentType.category,
            func.count(Booking.id).label("completed_bookings"),
            func.coalesce(
                func.sum(AppointmentType.duration_minutes), 0
            ).label("total_minutes"),
        )
        .join(AppointmentType, AppointmentType.id == Booking.appointment_type_id)
        .where(
            Booking.tenant_id == tenant.id,
            Booking.contact_id == contact_id,
            Booking.status == BookingStatus.COMPLETED,
        )
        .group_by(AppointmentType.id, AppointmentType.name, AppointmentType.category)
        .order_by(func.sum(AppointmentType.duration_minutes).desc())
    )).all()

    by_service = [
        VolunteerServiceStat(
            appointment_type_id=r[0],
            name=r[1],
            category=r[2],
            completed_bookings=int(r[3] or 0),
            total_minutes=int(r[4] or 0),
        )
        for r in rows
    ]
    return VolunteerStatsResponse(
        total_completed_bookings=sum(s.completed_bookings for s in by_service),
        total_minutes=sum(s.total_minutes for s in by_service),
        by_service=by_service,
    )


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


@router.get("/{phone}/recent-messages")
async def get_customer_recent_messages(
    phone: str,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    days: int = Query(7, ge=1, le=90),
):
    """Flat chronological list of {role, content, timestamp} from this volunteer's
    conversations, filtered to messages whose timestamp is within the last N days.
    Used by the test tools to seed history.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Conversation.message_history, Conversation.last_message_at)
        .where(
            Conversation.contact_phone == phone,
            Conversation.tenant_id == tenant.id,
            Conversation.last_message_at >= cutoff,
        )
        .order_by(Conversation.last_message_at.asc())
    )

    flat: list[dict] = []
    for history, last in result.all():
        if not history:
            continue
        # Some legacy / test-tool conversation entries don't carry a
        # per-message timestamp. Don't drop them — fall back to the
        # conversation's last_message_at so they still appear in the
        # rehydration. They'll just cluster at the same time, which is
        # acceptable for display.
        fallback_ts = last if isinstance(last, datetime) else None
        if fallback_ts and fallback_ts.tzinfo is None:
            fallback_ts = fallback_ts.replace(tzinfo=timezone.utc)
        for msg in history:
            ts_raw = msg.get("timestamp")
            ts: datetime | None = None
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(ts_raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    ts = None
            if ts is None:
                ts = fallback_ts
            if ts is None or ts < cutoff:
                continue
            role = msg.get("role")
            content = msg.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str):
                continue
            flat.append({"role": role, "content": content, "timestamp": ts.isoformat()})

    flat.sort(key=lambda m: m["timestamp"])
    return {"messages": flat, "days": days}


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
