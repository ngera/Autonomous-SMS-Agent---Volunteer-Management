import uuid
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, ManagerUser
from app.models.availability import AvailabilityRule, SpecificDateSlot
from app.models.blocked_date import BlockedDate
from app.schemas.availability import (
    AvailabilityRuleResponse,
    BlockedDateCreate,
    BlockedDateResponse,
    SlotResponse,
    SpecificDateSlotCreate,
    SpecificDateSlotResponse,
    SpecificDateSlotUpdate,
    WeeklyScheduleUpdate,
)
from app.schemas.booking import EventRosterEvent, EventRosterResponse

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])


def _serialize_service_config(data: dict) -> dict:
    """Convert service_config Pydantic models to dicts with str UUIDs for JSONB."""
    if data.get("service_config"):
        data["service_config"] = [
            {
                "appointment_type_id": str(c["appointment_type_id"]),
                "min_required": c["min_required"],
                "max_allowed": c["max_allowed"],
            }
            for c in data["service_config"]
        ]
    return data


# ── Weekly rules ──

@router.get("/rules", response_model=list[AvailabilityRuleResponse])
async def get_availability_rules(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(AvailabilityRule)
        .where(AvailabilityRule.tenant_id == tenant.id)
        .order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
    )
    return result.scalars().all()


@router.put("/rules", response_model=list[AvailabilityRuleResponse])
async def update_availability_rules(
    body: WeeklyScheduleUpdate, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    """Replace the weekly schedule with an upsert that preserves rule
    identity. Rules carrying an `id` are updated in place (which
    preserves the FK link to any SpecificDateSlot they've already
    materialized), rules without an `id` are inserted, and rules
    that disappear from the payload are deleted (which nulls the FK
    on materialized slots — they survive as standalone events).

    Whenever an existing rule's propagated fields change, the
    propagation engine fans the diff out to materialized future
    slots: safe slots absorb silently, unsafe slots get a "Rule
    changed — review" alert. See
    services.availability.propagate_rule_edit_to_materialized_slots.
    """
    from app.services.availability import (
        _PROPAGATED_RULE_FIELDS,
        cleanup_unused_materialized_slots,
        propagate_rule_edit_to_materialized_slots,
    )

    existing_rows = (await db.execute(
        select(AvailabilityRule).where(AvailabilityRule.tenant_id == tenant.id)
    )).scalars().all()
    existing_by_id: dict[uuid.UUID, AvailabilityRule] = {r.id: r for r in existing_rows}

    kept_ids: set[uuid.UUID] = set()
    edited_rules: list[AvailabilityRule] = []
    result_rules: list[AvailabilityRule] = []

    for rule_data in body.rules:
        data = _serialize_service_config(rule_data.model_dump())
        incoming_id = data.pop("id", None)
        if incoming_id and incoming_id in existing_by_id:
            rule = existing_by_id[incoming_id]
            # Snapshot the fields the propagation engine cares about so
            # we know whether to fan out after the update.
            before = {f: getattr(rule, f) for f in _PROPAGATED_RULE_FIELDS}
            for field, value in data.items():
                setattr(rule, field, value)
            after = {f: getattr(rule, f) for f in _PROPAGATED_RULE_FIELDS}
            if before != after:
                edited_rules.append(rule)
            kept_ids.add(rule.id)
            result_rules.append(rule)
        else:
            rule = AvailabilityRule(tenant_id=tenant.id, **data)
            db.add(rule)
            result_rules.append(rule)

    # Anything not kept is deleted. First scrub empty materialized
    # slots (no bookings, no campaigns) so they don't linger as
    # orphan "(unnamed)" rows after the FK SET NULL. Slots with
    # real state survive with their FK nulled.
    for old_id, old_rule in existing_by_id.items():
        if old_id not in kept_ids:
            await cleanup_unused_materialized_slots(db, tenant, old_id)
            await db.delete(old_rule)

    await db.flush()
    for rule in result_rules:
        await db.refresh(rule)

    # Propagate edits AFTER flush so the materialized-slot writes see
    # the rule's new values. Drift summaries point at the new state.
    for rule in edited_rules:
        await propagate_rule_edit_to_materialized_slots(db, tenant, rule)

    return result_rules


# ── Specific date slots / events ──

@router.get("/specific-slots", response_model=list[SpecificDateSlotResponse])
async def list_specific_date_slots(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(SpecificDateSlot)
        .where(SpecificDateSlot.tenant_id == tenant.id)
        .order_by(SpecificDateSlot.date, SpecificDateSlot.start_time)
    )
    return result.scalars().all()


async def _blocked_date_conflicts(
    db: DbSession, tenant_id: uuid.UUID, target: date
) -> list[BlockedDate]:
    """Return any blocked-date ranges that cover ``target`` for this tenant."""
    result = await db.execute(
        select(BlockedDate).where(
            BlockedDate.tenant_id == tenant_id,
            BlockedDate.date_from <= target,
            BlockedDate.date_to >= target,
        )
    )
    return list(result.scalars().all())


def _format_blocked_conflict(blocks: list[BlockedDate]) -> dict:
    """Build the 409 response body for a blocked-date / event conflict."""
    return {
        "code": "blocked_date_conflict",
        "message": (
            "This date is inside a blocked-date range. "
            "Confirm to schedule the event anyway."
        ),
        "blocked_dates": [
            {
                "date_from": b.date_from.isoformat(),
                "date_to": b.date_to.isoformat(),
                "reason": b.reason,
            }
            for b in blocks
        ],
    }


@router.post("/specific-slots", response_model=SpecificDateSlotResponse, status_code=status.HTTP_201_CREATED)
async def create_specific_date_slot(
    body: SpecificDateSlotCreate,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    force: bool = Query(False),
):
    if not force:
        conflicts = await _blocked_date_conflicts(db, tenant.id, body.date)
        if conflicts:
            raise HTTPException(status_code=409, detail=_format_blocked_conflict(conflicts))

    data = _serialize_service_config(body.model_dump())
    slot = SpecificDateSlot(tenant_id=tenant.id, **data)
    db.add(slot)
    await db.flush()
    await db.refresh(slot)
    return slot


@router.put("/specific-slots/{slot_id}", response_model=SpecificDateSlotResponse)
async def update_specific_date_slot(
    slot_id: uuid.UUID,
    body: SpecificDateSlotUpdate,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    force: bool = Query(False),
):
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id, SpecificDateSlot.tenant_id == tenant.id
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Specific date slot not found")

    # Only re-check the blocked-date conflict when the date itself changed —
    # rescheduling within the same blocked day shouldn't keep nagging the admin.
    update_data = _serialize_service_config(body.model_dump(exclude_unset=True))
    new_date = update_data.get("date")
    if not force and new_date and new_date != slot.date:
        conflicts = await _blocked_date_conflicts(db, tenant.id, new_date)
        if conflicts:
            raise HTTPException(status_code=409, detail=_format_blocked_conflict(conflicts))

    # Snapshot pre-edit values BEFORE applying updates so the cascade
    # can compute the date/time delta and decide whether to fan out.
    old_date = slot.date
    old_start = slot.start_time
    old_end = slot.end_time

    service_config_changed = "service_config" in update_data
    for field, value in update_data.items():
        setattr(slot, field, value)
    await db.flush()
    await db.refresh(slot)

    # Mirror volunteer-requirement changes into any active/pending
    # recruitment campaigns tied to this slot so the Campaigns page's
    # Goals stays in sync with the event's Roster section.
    if service_config_changed:
        from app.agents.recruiter import executor as recruiter_executor
        await recruiter_executor.sync_campaign_goals_from_slot(db, slot)

    # If the date or start/end time moved, cascade to existing bookings
    # and any active recruitment campaign. Without this, signups stay
    # at the old date (orphan bookings) and PLANNED waves keep firing
    # against the old schedule. See design_decisions.md #19.
    from app.services.event_reschedule import (
        cascade_slot_reschedule,
        schedule_reconfirmation_sms,
        slot_datetime_changed,
    )
    if slot_datetime_changed(
        old_date, old_start, old_end,
        update_data.get("date"),
        update_data.get("start_time"),
        update_data.get("end_time"),
    ):
        summary = await cascade_slot_reschedule(
            db, slot, old_date, old_start
        )
        # Commit before backgrounding the SMS fan-out so the task's own
        # session sees the new state (design_decisions.md #5). Returning
        # the slot afterwards still works — FastAPI's get_db commits
        # again at request end as a no-op.
        await db.commit()
        schedule_reconfirmation_sms(summary, slot.label or "event")

    return slot


@router.post(
    "/specific-slots/{slot_id}/apply-rule-drift",
    response_model=SpecificDateSlotResponse,
)
async def apply_rule_drift(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Apply the pending rule drift to this slot — overwrite the slot's
    propagated fields with the parent rule's current values, then clear
    the drift flag. The slot's existing bookings stay attached; the
    admin is acknowledging the schedule change is acceptable to the
    volunteers (typically because they've already been notified).

    Returns the updated slot. Surfaced by the "Rule changed — review"
    alert's Apply action.
    """
    from app.services.availability import _PROPAGATED_RULE_FIELDS

    slot = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id,
            SpecificDateSlot.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.availability_rule_id is None:
        raise HTTPException(
            status_code=400,
            detail="Slot was not materialized from a rule",
        )
    if slot.rule_drift_at is None:
        raise HTTPException(
            status_code=400,
            detail="No pending rule drift for this slot",
        )

    rule = (await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.id == slot.availability_rule_id,
            AvailabilityRule.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=410,
            detail=(
                "Parent rule no longer exists. Resolve via ignore-rule-drift "
                "or edit the slot manually."
            ),
        )

    for field in _PROPAGATED_RULE_FIELDS:
        setattr(slot, field, getattr(rule, field))
    slot.rule_drift_at = None
    slot.rule_drift_summary = None
    await db.flush()
    await db.refresh(slot)
    return slot


@router.post(
    "/specific-slots/{slot_id}/ignore-rule-drift",
    response_model=SpecificDateSlotResponse,
)
async def ignore_rule_drift(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Mark the pending rule drift as resolved without touching the
    slot's own values. The admin's intent: this slot stays as-is, the
    rule change applies only to future occurrences."""
    slot = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id,
            SpecificDateSlot.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.rule_drift_at is None:
        raise HTTPException(
            status_code=400,
            detail="No pending rule drift for this slot",
        )
    slot.rule_drift_at = None
    slot.rule_drift_summary = None
    await db.flush()
    await db.refresh(slot)
    return slot


@router.delete("/specific-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specific_date_slot(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    force: bool = Query(False),
):
    """Delete a specific-date slot.

    Cascade rules:
      - Attached campaigns are slot-derivatives — deleted automatically
        (recruitment_campaigns.event_slot_id is RESTRICT, so leaving
        them attached would block the slot delete). Waves and signups
        cascade through the campaign's own ON DELETE CASCADE.
      - Non-cancelled bookings block the delete with a 409 unless
        `force=true` is passed. With force the bookings are flipped to
        CANCELLED first so the volunteer history survives — the FK
        from Booking → slot is SET NULL, so the row persists.
      - Cancelled bookings, roster pings, candidates, recognitions all
        use SET NULL / CASCADE already and don't need any pre-work.
    """
    from app.models.booking import Booking, BookingStatus
    from app.models.contact import Contact
    from app.models.recruitment_campaign import RecruitmentCampaign

    slot = (await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id,
            SpecificDateSlot.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Specific date slot not found")

    if not force:
        booking_rows = (await db.execute(
            select(Booking, Contact)
            .join(Contact, Contact.id == Booking.contact_id)
            .where(
                Booking.event_slot_id == slot_id,
                Booking.status != BookingStatus.CANCELLED,
            )
            .limit(5)
        )).all()
        if booking_rows:
            count = (await db.execute(
                select(func.count()).where(
                    Booking.event_slot_id == slot_id,
                    Booking.status != BookingStatus.CANCELLED,
                )
            )).scalar() or 0
            first_names = [
                ((c.name or c.phone or "").split() + [""])[0]
                for _, c in booking_rows
            ]
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "bookings_attached",
                    "message": (
                        f"{count} volunteer{'s' if count != 1 else ''} "
                        f"booked. Confirm to cancel them and delete the event."
                    ),
                    "booking_count": count,
                    "first_volunteer_names": first_names,
                },
            )

    # force=True OR no bookings — proceed.
    if force:
        active_bookings = (await db.execute(
            select(Booking).where(
                Booking.event_slot_id == slot_id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )).scalars().all()
        for b in active_bookings:
            b.status = BookingStatus.CANCELLED
        if active_bookings:
            await db.flush()

    campaigns = (await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.event_slot_id == slot_id,
        )
    )).scalars().all()
    for camp in campaigns:
        await db.delete(camp)
    if campaigns:
        await db.flush()

    await db.delete(slot)


# ── Blocked dates ──

@router.get("/blocked-dates", response_model=list[BlockedDateResponse])
async def get_blocked_dates(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(BlockedDate).where(BlockedDate.tenant_id == tenant.id).order_by(BlockedDate.date_from)
    )
    return result.scalars().all()


@router.post("/blocked-dates", response_model=BlockedDateResponse, status_code=status.HTTP_201_CREATED)
async def create_blocked_date(
    body: BlockedDateCreate,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
    force: bool = Query(False),
):
    if not force:
        # Surface any specific-date events that fall inside the blocked range
        # so the admin can decide whether to proceed.
        events = await db.execute(
            select(SpecificDateSlot).where(
                SpecificDateSlot.tenant_id == tenant.id,
                SpecificDateSlot.date >= body.date_from,
                SpecificDateSlot.date <= body.date_to,
                SpecificDateSlot.is_active.is_(True),
            )
        )
        conflicting = list(events.scalars().all())
        if conflicting:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "events_inside_block",
                    "message": (
                        "Specific-date events fall inside this blocked range. "
                        "They will keep running unless you cancel them; "
                        "confirm to add the block anyway."
                    ),
                    "events": [
                        {
                            "id": str(e.id),
                            "date": e.date.isoformat(),
                            "label": e.label,
                            "start_time": e.start_time.strftime("%H:%M"),
                            "end_time": e.end_time.strftime("%H:%M"),
                        }
                        for e in conflicting
                    ],
                },
            )

    blocked = BlockedDate(tenant_id=tenant.id, **body.model_dump())
    db.add(blocked)
    await db.flush()
    await db.refresh(blocked)
    return blocked


@router.delete("/blocked-dates/{blocked_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blocked_date(
    blocked_id: uuid.UUID, db: DbSession, current_user: ManagerUser, tenant: CurrentTenant
):
    result = await db.execute(
        select(BlockedDate).where(BlockedDate.id == blocked_id, BlockedDate.tenant_id == tenant.id)
    )
    blocked = result.scalar_one_or_none()
    if not blocked:
        raise HTTPException(status_code=404, detail="Blocked date not found")
    await db.delete(blocked)


# ── Event roster (source-based, works with zero bookings) ──


@router.get(
    "/specific-slots/{slot_id}/event-roster",
    response_model=EventRosterResponse,
)
async def get_specific_slot_event_roster(
    slot_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Return the full roster for a specific-date event, even with no bookings."""
    import pytz

    from app.api.bookings import build_event_roster_response

    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.id == slot_id,
            SpecificDateSlot.tenant_id == tenant.id,
        )
    )
    sds = result.scalar_one_or_none()
    if not sds:
        raise HTTPException(status_code=404, detail="Specific date slot not found")

    tz = pytz.timezone(tenant.business_timezone or "America/New_York")
    slot_start_local = tz.localize(datetime.combine(sds.date, sds.start_time))
    slot_end_local = tz.localize(datetime.combine(sds.date, sds.end_time))
    event_meta = EventRosterEvent(
        source="specific_date",
        source_id=sds.id,
        label=sds.label,
        location=sds.location,
        date=sds.date,
        start_time=sds.start_time,
        end_time=sds.end_time,
    )
    return await build_event_roster_response(
        db,
        tenant,
        service_config=sds.service_config,
        slot_start_local=slot_start_local,
        slot_end_local=slot_end_local,
        event_meta=event_meta,
    )


@router.get(
    "/rules/{rule_id}/event-roster",
    response_model=EventRosterResponse,
)
async def get_weekly_rule_event_roster(
    rule_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    on_date: date = Query(..., alias="date"),
):
    """Return the roster for one occurrence of a weekly window, even with no bookings.

    ``date`` selects which day-of-week occurrence to materialize. The rule's
    day_of_week must match the date's weekday or the request is rejected so
    admins don't accidentally view a non-existent occurrence.
    """
    import pytz

    from app.api.bookings import build_event_roster_response

    result = await db.execute(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id,
            AvailabilityRule.tenant_id == tenant.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Availability rule not found")
    if rule.day_of_week != on_date.weekday():
        raise HTTPException(
            status_code=400,
            detail=(
                f"This rule fires on day-of-week {rule.day_of_week} "
                f"but {on_date} is day-of-week {on_date.weekday()}."
            ),
        )

    tz = pytz.timezone(tenant.business_timezone or "America/New_York")
    slot_start_local = tz.localize(datetime.combine(on_date, rule.start_time))
    slot_end_local = tz.localize(datetime.combine(on_date, rule.end_time))
    event_meta = EventRosterEvent(
        source="weekly_rule",
        source_id=rule.id,
        label=rule.label,
        location=rule.location,
        date=on_date,
        start_time=rule.start_time,
        end_time=rule.end_time,
    )
    return await build_event_roster_response(
        db,
        tenant,
        service_config=rule.service_config,
        slot_start_local=slot_start_local,
        slot_end_local=slot_end_local,
        event_meta=event_meta,
    )


# ── Slot preview ──

@router.get("/slots", response_model=list[SlotResponse])
async def get_available_slots(
    db: DbSession, current_user: CurrentUser, tenant: CurrentTenant,
    date_param: date = Query(..., alias="date"),
    appointment_type_id: uuid.UUID = Query(...),
):
    from app.services.availability import compute_available_slots
    return await compute_available_slots(
        db=db, target_date=date_param, appointment_type_id=str(appointment_type_id), tenant=tenant,
    )
