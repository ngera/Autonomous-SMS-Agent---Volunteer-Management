"""Side-effecting layer for the Recruitment Agent.

The executor performs the actions chosen by ``scheduler_engine.next_action``
and the lifecycle steps for the SMS planning flow. Nothing in this module
reads policy — that's the planner's job — but it writes campaign/wave/
announcement rows and dispatches SMS.

All public functions are async and assume an ``AsyncSession`` is provided
by the caller (background-task callers open their own).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.recruiter import targeting
from app.api.announcements import _append_announcement_to_history
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.announcement import (
    Announcement,
    AnnouncementStatus,
    RecipientScope,
)
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationStatus
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)
from app.models.tenant import Tenant
from app.prompts.conversation import (
    get_announcement_header_template,
    get_recruitment_message_template,
)
from app.services.sms import send_sms

logger = get_logger("recruiter.executor")


DEFAULT_WAVE_OFFSETS_DAYS = [14, 7, 3, 1]
DEFAULT_MESSAGE_TEMPLATE = (
    "Hi{name_part}, we're looking for volunteers for {event_label} on "
    "{event_date}. Reply YES to sign up or STOP to opt out."
)


def _render_template(
    template: str, contact: Contact, event_context: dict
) -> str:
    """Render a message template with the supported personalization tokens.

    Tokens: ``{first_name}``, ``{name_part}``, ``{event_label}``,
    ``{event_date}``, ``{event_start_time}``, ``{event_end_time}``,
    ``{hours}`` (computed event duration in hours, e.g. "2" or "1.5"),
    ``{event_location}``, ``{service_name}``. Missing tokens are silently
    rendered as empty strings to avoid send failures.
    """
    first_name = ""
    if contact.name:
        first_name = contact.name.split()[0]

    class _Defaulting(dict):
        def __missing__(self, key: str) -> str:
            return ""

    start = event_context.get("event_start_time", "") or ""
    end = event_context.get("event_end_time", "") or ""
    hours_str = _compute_hours_label(start, end)

    ctx = _Defaulting(
        first_name=first_name,
        # Convenience computed field: " <name>" when name exists; empty
        # otherwise. Use as "Hi{name_part}," for graceful fallback.
        name_part=f" {first_name}" if first_name else "",
        event_label=event_context.get("event_label", "") or "",
        event_date=event_context.get("event_date", "") or "",
        event_start_time=start,
        event_end_time=end,
        hours=hours_str,
        event_location=event_context.get("event_location", "") or "",
        service_name=event_context.get("service_name", "") or "",
    )
    try:
        return template.format_map(ctx)
    except (ValueError, IndexError):
        return template


def _compute_hours_label(start: str, end: str) -> str:
    """Render an event duration as a compact "Nh" / "N.5h" string.

    Returns "" if either time is missing or unparseable. Avoids depending
    on dateutil — both inputs are HH:MM strings.
    """
    if not start or not end:
        return ""
    try:
        sh, sm = (int(x) for x in start.split(":")[:2])
        eh, em = (int(x) for x in end.split(":")[:2])
    except (ValueError, AttributeError):
        return ""
    minutes = (eh * 60 + em) - (sh * 60 + sm)
    # Handle wrap-past-midnight gracefully: assume next-day.
    if minutes <= 0:
        minutes += 24 * 60
    hours = minutes / 60
    if hours.is_integer():
        return f"{int(hours)}"
    return f"{hours:.1f}".rstrip("0").rstrip(".")


async def _build_event_context(
    db: AsyncSession,
    event_slot: SpecificDateSlot,
    service_id: uuid.UUID,
) -> dict:
    appt_type = await db.get(AppointmentType, service_id)
    return {
        "event_label": event_slot.label or (appt_type.name if appt_type else ""),
        "event_date": event_slot.date.isoformat(),
        "event_start_time": event_slot.start_time.strftime("%H:%M")
        if event_slot.start_time
        else "",
        "event_end_time": event_slot.end_time.strftime("%H:%M")
        if event_slot.end_time
        else "",
        "event_location": event_slot.location or "",
        "service_name": appt_type.name if appt_type else "",
        "appointment_type_id": str(service_id),
    }


async def materialize_waves_on_approval(
    db: AsyncSession,
    campaign: RecruitmentCampaign,
    event_slot: SpecificDateSlot,
) -> list[RecruitmentWave]:
    """Create RecruitmentWave rows from policy.wave_offsets_days at approval.

    One wave per (service, offset). ``scheduled_at`` is computed as the
    event start datetime minus the offset days. Offsets in the past (e.g.
    the campaign was approved less than 14 days before the event) are
    snapped to ``now`` so they fire on the next tick.

    Existing waves for the campaign are left untouched — callers that need
    a clean re-materialize should delete them first.
    """
    policy = campaign.policy or {}
    offsets = list(
        policy.get("wave_offsets_days") or DEFAULT_WAVE_OFFSETS_DAYS
    )
    goals = campaign.goals or []
    if not goals or not offsets:
        return []

    # Event datetime (use start time if present, else midnight UTC of event date)
    event_dt = datetime.combine(
        event_slot.date,
        event_slot.start_time or datetime.min.time(),
        tzinfo=timezone.utc,
    )
    now = datetime.now(timezone.utc)

    created: list[RecruitmentWave] = []
    for goal in goals:
        service_id = goal.get("appointment_type_id")
        if not service_id:
            continue
        try:
            service_uuid = uuid.UUID(str(service_id))
        except (ValueError, TypeError):
            continue
        # Order offsets descending so wave_number 1 is the earliest send
        sorted_offsets = sorted(offsets, reverse=True)
        for idx, offset_days in enumerate(sorted_offsets, start=1):
            scheduled_at = event_dt - timedelta(days=int(offset_days))
            # Wave 1 always fires immediately on approval — admin shouldn't
            # have to wait days for outreach to start when the policy's
            # first offset (e.g. T-14) is far in the future. Subsequent
            # waves keep their relative spacing from the event.
            if idx == 1 or scheduled_at < now:
                scheduled_at = now
            wave = RecruitmentWave(
                tenant_id=campaign.tenant_id,
                campaign_id=campaign.id,
                wave_number=idx,
                appointment_type_id=service_uuid,
                status=WaveStatus.PLANNED,
                scheduled_at=scheduled_at,
            )
            db.add(wave)
            created.append(wave)
    await db.flush()
    return created


async def execute_send_wave(
    db: AsyncSession,
    tenant: Tenant,
    campaign: RecruitmentCampaign,
    wave: RecruitmentWave,
    event_slot: SpecificDateSlot,
    phase: str = "min",
) -> None:
    """Resolve targets, render messages, fire SMS, link Announcement.

    ``phase`` decides which target to size the wave against:
    - ``min``: fill toward ``min_required``.
    - ``max``: fill toward ``max_allowed`` (after min is satisfied
      cross-campaign).
    Idempotent guard: if the wave is no longer ``PLANNED`` this is a no-op.
    """
    if wave.status != WaveStatus.PLANNED:
        return

    # Resolve recipients fresh at send time (captures late opt-ins)
    result = await targeting.select_recipients(
        db,
        campaign=campaign,
        event_slot=event_slot,
        service_id=wave.appointment_type_id,
        wave_number=wave.wave_number,
        phase=phase,  # type: ignore[arg-type]
    )

    if not result.contacts:
        wave.status = WaveStatus.SKIPPED
        wave.selection_reason = result.selection_reason
        wave.sent_count = 0
        await db.flush()
        logger.info(
            "Wave %s skipped: %s", wave.id, result.selection_reason
        )
        return

    # Mark sending up front so a crash mid-flight doesn't leave PLANNED.
    wave.status = WaveStatus.SENDING
    wave.targeted_contact_ids = [str(c.contact_id) for c in result.contacts]
    wave.selection_reason = result.selection_reason
    await db.flush()

    # Build event_context for the announcement header
    event_context = await _build_event_context(
        db, event_slot, wave.appointment_type_id
    )

    # Pick the message template for this wave_number, falling back first
    # to the campaign's "default" entry, then to the per-tenant default
    # configured on the Templates page (Settings → Templates → Recruitment
    # Agent message), then to the shipped constant.
    templates = campaign.message_templates or {}
    template = (
        templates.get(str(wave.wave_number))
        or templates.get("default")
        or await get_recruitment_message_template(db, tenant.id)
    )

    # Create the Announcement row for audit linkage; status starts SENDING
    # since we drive the send loop directly (not via _send_announcement).
    ann = Announcement(
        tenant_id=tenant.id,
        message=template,
        filter_appointment_type_ids=[str(wave.appointment_type_id)],
        recipient_scope=RecipientScope.ALL.value,
        scheduled_at=None,
        status=AnnouncementStatus.SENDING,
        event_context=event_context,
        created_by_admin_id=campaign.created_by_admin_id,
        recruitment_wave_id=wave.id,
        total_recipients=len(result.contacts),
    )
    db.add(ann)
    await db.flush()
    wave.announcement_id = ann.id

    header_template = await get_announcement_header_template(db, tenant.id)

    # Load full Contact rows for personalization tokens
    contacts = await db.execute(
        select(Contact).where(
            Contact.id.in_([c.contact_id for c in result.contacts])
        )
    )
    contact_rows: list[Contact] = list(contacts.scalars().all())
    by_id = {c.id: c for c in contact_rows}

    sent = 0
    failed = 0
    for sc in result.contacts:
        contact = by_id.get(sc.contact_id)
        if not contact:
            failed += 1
            continue
        body = _render_template(template, contact, event_context)
        # Prepend the standard event header so volunteers see date/time/location
        full_message = _render_with_event_header(
            header_template, event_context, body
        )
        try:
            ok = await send_sms(contact.phone, full_message, tenant)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Recruitment wave SMS failed: wave=%s contact=%s",
                wave.id, contact.id,
            )
            ok = False
        if ok:
            sent += 1
            try:
                await _append_announcement_to_history(
                    db,
                    tenant.id,
                    contact.phone,
                    full_message,
                    datetime.now(timezone.utc),
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to append recruitment SMS to history: %s",
                    contact.phone,
                )
        else:
            failed += 1

    ann.sent_count = sent
    ann.failed_count = failed
    ann.sent_at = datetime.now(timezone.utc)
    ann.status = (
        AnnouncementStatus.SENT if failed == 0 else AnnouncementStatus.FAILED
    )
    wave.sent_count = sent
    wave.status = WaveStatus.SENT
    await db.flush()
    logger.info(
        "Wave %s sent: %d/%d delivered", wave.id, sent, len(result.contacts)
    )


def _render_with_event_header(
    header_template: str, event_context: dict, body: str
) -> str:
    """Reuse the existing announcement-header formatting rule.

    Mirrors ``_render_announcement_message`` in ``app/api/announcements.py``
    but copied here to avoid a circular import (executor → announcements →
    something deep). The two formatters MUST stay in sync; if you change
    one, change the other.
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
        header = header_template.format_map(ctx)
    except (ValueError, KeyError, IndexError):
        header = ""
    return f"{header}{body}"


async def send_planning_followup_sms(
    db: AsyncSession,
    tenant: Tenant,
    campaign: RecruitmentCampaign,
    admin_phone: str,
    summary: str,
) -> None:
    """Async SMS planning flow step 3: text admin the plan summary.

    Also mirrors the outgoing message into the admin's
    ``sender_type='admin'`` conversation history so it appears in the
    test-conversation view (locked decision #2).
    """
    body = (summary or "Recruitment plan ready.").strip()
    # Truncate to keep within SMS-friendly bounds while leaving room for
    # the approve hint.
    if len(body) > 380:
        body = body[:377].rstrip() + "..."
    body += "\n\nReply APPROVE to start, or open the dashboard to edit."
    try:
        await send_sms(admin_phone, body, tenant)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to send planning follow-up SMS: campaign=%s phone=%s",
            campaign.id, admin_phone,
        )
        return
    await _append_to_admin_conversation(db, tenant.id, admin_phone, body)


async def send_planning_error_sms(
    db: AsyncSession,
    tenant: Tenant,
    admin_phone: str,
    event_label: str,
) -> None:
    body = (
        f"Recruitment planning for {event_label} failed. "
        "Open the dashboard to try again or contact support."
    )
    try:
        await send_sms(admin_phone, body, tenant)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send planning error SMS")
        return
    await _append_to_admin_conversation(db, tenant.id, admin_phone, body)


async def _append_to_admin_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    admin_phone: str,
    body: str,
) -> None:
    """Append an outgoing system SMS to the admin's conversation history.

    Mirrors ``_append_announcement_to_history`` shape, but scoped to
    ``sender_type='admin'`` so the message shows up in the admin's
    test-conversation view rather than a volunteer panel.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.contact_phone == admin_phone,
            Conversation.status == ConversationStatus.ACTIVE,
            Conversation.sender_type == "admin",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    convo = result.scalar_one_or_none()
    if not convo:
        convo = Conversation(
            tenant_id=tenant_id,
            contact_phone=admin_phone,
            contact_id=None,
            sender_type="admin",
            message_history=[],
            status=ConversationStatus.ACTIVE,
            current_step="recruitment",
            last_message_at=now,
        )
        db.add(convo)
        await db.flush()

    history = list(convo.message_history or [])
    history.append(
        {
            "role": "assistant",
            "content": body,
            "timestamp": now.isoformat(),
            "kind": "recruitment_report",
        }
    )
    from app.modules.conversation import trim_message_history
    convo.message_history = trim_message_history(history)
    convo.last_message_at = now
    await db.flush()


async def current_signups_per_service(
    db: AsyncSession,
    event_slot: SpecificDateSlot,
    service_ids: list[uuid.UUID],
) -> dict[str, int]:
    """Compute the fill snapshot used by ``scheduler_engine.next_action``.

    One small query rather than N: group by appointment_type_id and only
    count SCHEDULED + RESCHEDULED bookings on the event date.
    """
    if not service_ids:
        return {}
    result = await db.execute(
        select(Booking.appointment_type_id, func.count(Booking.id))
        .where(
            Booking.tenant_id == event_slot.tenant_id,
            Booking.appointment_type_id.in_(service_ids),
            func.date(Booking.scheduled_at) == event_slot.date,
            Booking.status.in_(
                [BookingStatus.SCHEDULED, BookingStatus.RESCHEDULED]
            ),
        )
        .group_by(Booking.appointment_type_id)
    )
    out: dict[str, int] = {str(sid): 0 for sid in service_ids}
    for sid, count in result.all():
        out[str(sid)] = int(count)
    return out


async def mark_campaign_completed(
    db: AsyncSession, campaign: RecruitmentCampaign, reason: str
) -> None:
    campaign.status = CampaignStatus.COMPLETED
    await db.flush()
    logger.info("Campaign %s completed: %s", campaign.id, reason)


async def run_tick_for_campaign(campaign_id: uuid.UUID) -> None:
    """Run the recruitment tick for a single campaign immediately.

    Used right after approval so the first wave fires within seconds
    instead of waiting up to 15 min for the next scheduled tick. Opens
    its own DB session — safe to call from a background task.
    """
    from app.agents.recruiter import scheduler_engine
    from app.models.availability import SpecificDateSlot
    from app.models.recruitment_campaign import (
        RecruitmentCampaign as _Campaign,
        RecruitmentWave as _Wave,
    )
    from app.models.tenant import Tenant as _Tenant

    async with async_session_factory() as db:
        try:
            campaign = await db.get(_Campaign, campaign_id)
            if not campaign or campaign.status != CampaignStatus.ACTIVE:
                return
            tenant = await db.get(_Tenant, campaign.tenant_id)
            slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
            if not tenant or not slot:
                return

            # Compute fill snapshot for this campaign's services.
            service_ids = [
                uuid.UUID(g["appointment_type_id"])
                for g in campaign.goals or []
                if g.get("appointment_type_id")
            ]
            fill = scheduler_engine.FillSnapshot(
                per_service=await current_signups_per_service(
                    db, slot, service_ids
                )
            )

            # Compute global per-service min-phase set across this tenant.
            tenant_campaigns_q = await db.execute(
                select(_Campaign).where(
                    _Campaign.tenant_id == tenant.id,
                    _Campaign.status == CampaignStatus.ACTIVE,
                )
            )
            min_phase_service_ids: set[str] = set()
            for c in tenant_campaigns_q.scalars().all():
                c_service_ids = [
                    uuid.UUID(g["appointment_type_id"])
                    for g in c.goals or []
                    if g.get("appointment_type_id")
                ]
                # Reuse this campaign's slot for fill if same campaign;
                # otherwise compute per its own slot.
                if c.id == campaign.id:
                    c_fill = fill.per_service
                else:
                    c_slot = await db.get(SpecificDateSlot, c.event_slot_id)
                    if not c_slot:
                        continue
                    c_fill = await current_signups_per_service(
                        db, c_slot, c_service_ids
                    )
                for goal in c.goals or []:
                    sid = goal.get("appointment_type_id")
                    if not sid:
                        continue
                    min_req = (
                        goal.get("min_required")
                        if goal.get("min_required") is not None
                        else goal.get("min_acceptable")
                        if goal.get("min_acceptable") is not None
                        else goal.get("target", 0)
                    )
                    try:
                        min_int = int(min_req or 0)
                    except (TypeError, ValueError):
                        min_int = 0
                    if c_fill.get(str(sid), 0) < min_int:
                        min_phase_service_ids.add(str(sid))

            event_dt = datetime.combine(
                slot.date,
                slot.start_time or datetime.min.time(),
                tzinfo=timezone.utc,
            )

            # Drain due waves — the standard tick fires one wave per
            # campaign per 15-min cycle, but on a fresh approval it's
            # reasonable to drain all currently-due waves so the campaign
            # gets fully started rather than dribbling out over multiple
            # ticks.
            for _ in range(20):  # safety cap
                waves_q = await db.execute(
                    select(_Wave).where(_Wave.campaign_id == campaign.id)
                )
                waves = list(waves_q.scalars().all())
                action = scheduler_engine.next_action(
                    campaign,
                    waves,
                    fill,
                    event_dt,
                    min_phase_service_ids=min_phase_service_ids,
                )
                if action.kind != scheduler_engine.ActionKind.SEND_WAVE:
                    if action.kind == scheduler_engine.ActionKind.COMPLETE:
                        await mark_campaign_completed(db, campaign, action.reason)
                    break
                wave = next(
                    (w for w in waves if w.id == action.wave_id), None
                )
                if not wave:
                    break
                await execute_send_wave(
                    db, tenant, campaign, wave, slot, phase=action.phase
                )
                # Refresh fill so the next iteration sees the updated state.
                fill = scheduler_engine.FillSnapshot(
                    per_service=await current_signups_per_service(
                        db, slot, service_ids
                    )
                )
            await db.commit()
            logger.info(
                "Immediate-tick complete for campaign %s", campaign_id
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Immediate-tick failed for campaign %s", campaign_id
            )


async def mark_campaign_paused(
    db: AsyncSession, campaign: RecruitmentCampaign, reason: str
) -> None:
    campaign.status = CampaignStatus.PAUSED
    await db.flush()
    logger.warning("Campaign %s paused: %s", campaign.id, reason)


def goals_from_slot(
    slot: SpecificDateSlot, override_min: int | None = None
) -> list[dict]:
    """Canonical derivation of recruitment goals from a slot.

    Each goal carries both ``min_required`` (must-fill, drives min phase)
    and ``max_allowed`` (ceiling, drives max phase; null means no max
    phase). When ``override_min`` is set, it replaces ``min_required`` for
    all services. Used at campaign creation AND when syncing goals after
    a slot's service_config changes.
    """
    goals: list[dict] = []
    for entry in slot.service_config or []:
        sid = entry.get("appointment_type_id")
        if not sid:
            continue
        slot_min = int(entry.get("min_required", 1))
        slot_max = entry.get("max_allowed")
        try:
            slot_max_int: int | None = (
                int(slot_max) if slot_max is not None else None
            )
        except (TypeError, ValueError):
            slot_max_int = None
        min_required = (
            override_min if override_min is not None else slot_min
        )
        goals.append(
            {
                "appointment_type_id": str(sid),
                "min_required": int(min_required),
                "max_allowed": slot_max_int,
            }
        )
    return goals


async def sync_campaign_goals_from_slot(
    db: AsyncSession, slot: SpecificDateSlot
) -> int:
    """Propagate slot.service_config changes to all linked active campaigns.

    Recruitment goals are derived from the event's volunteer requirements,
    so when the admin edits min_required / max_allowed / adds or removes
    services on the slot, every campaign that's still working that event
    needs its ``goals`` updated. Returns the number of campaigns synced.

    Terminal campaigns (completed/cancelled/failed) are left alone — their
    goals are historical record.
    """
    new_goals = goals_from_slot(slot)
    q = await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == slot.tenant_id,
            RecruitmentCampaign.event_slot_id == slot.id,
            RecruitmentCampaign.status.in_(
                [
                    CampaignStatus.DRAFT,
                    CampaignStatus.AWAITING_APPROVAL,
                    CampaignStatus.ACTIVE,
                    CampaignStatus.PAUSED,
                ]
            ),
        )
    )
    campaigns = list(q.scalars().all())
    for c in campaigns:
        c.goals = new_goals
    if campaigns:
        await db.flush()
        logger.info(
            "Synced goals from slot %s to %d campaign(s)",
            slot.id, len(campaigns),
        )
    return len(campaigns)
