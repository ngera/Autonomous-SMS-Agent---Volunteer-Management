"""Recruitment Agent REST API.

Endpoints under /api/v1/recruitment/ for managing recruitment campaigns:
create (kicks off the planner as a background task), list, detail,
approve / pause / resume / cancel, regenerate the plan, edit message
templates pre-approval, and cancel an individual wave.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import desc, func, select

from app.agents.recruiter import executor, planner
from app.core.dependencies import (
    CurrentTenant,
    CurrentUser,
    DbSession,
    ManagerUser,
)
from app.core.logging import get_logger
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentReport,
    RecruitmentWave,
    WaveStatus,
)
from app.schemas.recruitment import (
    CampaignCreate,
    CampaignDetailResponse,
    CampaignListItem,
    CampaignListResponse,
    CampaignPlanPatch,
    CampaignResponse,
    WaveResponse,
)

logger = get_logger("api.recruitment")

router = APIRouter(prefix="/api/v1/recruitment", tags=["recruitment"])


AT_RISK_DAYS_REMAINING = 3
AT_RISK_FILL_PCT_BELOW = 0.75


async def _load_event_slot(
    db, tenant_id: uuid.UUID, slot_id: uuid.UUID
) -> SpecificDateSlot:
    slot = await db.get(SpecificDateSlot, slot_id)
    if not slot or slot.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Event slot not found")
    return slot


def _goals_from_slot(slot: SpecificDateSlot) -> list[dict]:
    """Derive goals from the slot's service_config when admin omits them.

    Each goal preserves both ``min_required`` (must-fill, drives min phase)
    and ``max_allowed`` (ceiling, drives max phase). When the slot doesn't
    set max_allowed, recruitment stops at min_required.
    """
    goals: list[dict] = []
    for entry in slot.service_config or []:
        type_id = entry.get("appointment_type_id")
        if not type_id:
            continue
        max_allowed = entry.get("max_allowed")
        try:
            max_int: int | None = (
                int(max_allowed) if max_allowed is not None else None
            )
        except (TypeError, ValueError):
            max_int = None
        goals.append(
            {
                "appointment_type_id": str(type_id),
                "min_required": int(entry.get("min_required", 1)),
                "max_allowed": max_int,
            }
        )
    return goals


async def _kick_off_planner(campaign_id: uuid.UUID, admin_phone: str | None) -> None:
    """Background task: run the planner, then SMS the admin if we have a phone."""
    summary = await planner.run_planner(campaign_id)
    if not admin_phone:
        return
    # Re-open a session to send the SMS — planner already closed its own.
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        campaign = await db.get(RecruitmentCampaign, campaign_id)
        if not campaign:
            return
        from app.models.tenant import Tenant
        tenant = await db.get(Tenant, campaign.tenant_id)
        if not tenant:
            return
        if not summary:
            # Planner failed → tell the admin so they know it didn't silently die
            from app.models.availability import SpecificDateSlot
            slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
            await executor.send_planning_error_sms(
                db, tenant, admin_phone, slot.label or "event" if slot else "event"
            )
            await db.commit()
            return
        await executor.send_planning_followup_sms(
            db, tenant, campaign, admin_phone, summary
        )
        await db.commit()


# ── Create / plan management ──


@router.post(
    "/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    body: CampaignCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Create a DRAFT campaign and kick the planner off in the background.

    Returns immediately with status=draft; the planner flips status to
    awaiting_approval and writes plan_summary/plan_preview asynchronously.
    """
    # Verify slot exists in this tenant
    slot = await _load_event_slot(db, tenant.id, body.event_slot_id)

    # Reject if an active/awaiting-approval campaign already exists for this slot
    existing_q = await db.execute(
        select(RecruitmentCampaign).where(
            RecruitmentCampaign.tenant_id == tenant.id,
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
    if existing_q.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An active or pending campaign already exists for this event.",
        )

    goals = (
        [g.model_dump(mode="json") for g in body.goals]
        if body.goals
        else _goals_from_slot(slot)
    )
    if not goals:
        raise HTTPException(
            status_code=400,
            detail="Event has no service_config and no goals were provided.",
        )

    campaign = RecruitmentCampaign(
        tenant_id=tenant.id,
        event_slot_id=slot.id,
        status=CampaignStatus.DRAFT,
        goals=goals,
        policy={},  # planner populates
        created_by_admin_id=current_user.id,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)

    background_tasks.add_task(
        _kick_off_planner, campaign.id, current_user.phone
    )
    return campaign


@router.post(
    "/campaigns/{campaign_id}/regenerate-plan",
    response_model=CampaignResponse,
)
async def regenerate_plan(
    campaign_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status not in (
        CampaignStatus.DRAFT,
        CampaignStatus.AWAITING_APPROVAL,
        CampaignStatus.FAILED,
    ):
        raise HTTPException(
            status_code=400,
            detail="Plan can only be regenerated before approval.",
        )
    campaign.status = CampaignStatus.DRAFT
    campaign.plan_summary = None
    campaign.plan_preview = None
    await db.flush()
    await db.refresh(campaign)
    background_tasks.add_task(
        _kick_off_planner, campaign.id, current_user.phone
    )
    return campaign


@router.patch("/campaigns/{campaign_id}/plan", response_model=CampaignResponse)
async def edit_plan(
    campaign_id: uuid.UUID,
    body: CampaignPlanPatch,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status != CampaignStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail="Plan edits are only allowed while awaiting approval.",
        )
    if body.policy is not None:
        campaign.policy = {**(campaign.policy or {}), **body.policy}
    if body.message_templates is not None:
        campaign.message_templates = body.message_templates
    await db.flush()
    await db.refresh(campaign)
    return campaign


# ── Lifecycle (approve / pause / resume / cancel) ──


@router.post("/campaigns/{campaign_id}/approve", response_model=CampaignResponse)
async def approve_campaign(
    campaign_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status != CampaignStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve a campaign in status {campaign.status.value}.",
        )
    slot = await _load_event_slot(db, tenant.id, campaign.event_slot_id)

    campaign.status = CampaignStatus.ACTIVE
    campaign.approved_by_admin_id = current_user.id
    campaign.approved_at = datetime.now(timezone.utc)
    await db.flush()

    await executor.materialize_waves_on_approval(db, campaign, slot)
    await db.flush()
    await db.refresh(campaign)

    # Run a tick for this campaign right away so the first wave fires
    # immediately. BackgroundTasks runs after the response is sent (and
    # after FastAPI commits), so the tick task sees the approved row.
    background_tasks.add_task(executor.run_tick_for_campaign, campaign.id)
    return campaign


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status != CampaignStatus.ACTIVE:
        raise HTTPException(
            status_code=400, detail="Only ACTIVE campaigns can be paused."
        )
    campaign.status = CampaignStatus.PAUSED
    await db.flush()
    await db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status != CampaignStatus.PAUSED:
        raise HTTPException(
            status_code=400, detail="Only PAUSED campaigns can be resumed."
        )
    campaign.status = CampaignStatus.ACTIVE
    await db.flush()
    await db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status in (
        CampaignStatus.COMPLETED,
        CampaignStatus.CANCELLED,
        CampaignStatus.FAILED,
    ):
        raise HTTPException(
            status_code=400, detail="Campaign already in a terminal state."
        )
    campaign.status = CampaignStatus.CANCELLED
    # Cancel any pending waves so the tick doesn't pick them up
    await db.execute(
        RecruitmentWave.__table__.update()
        .where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.PLANNED,
        )
        .values(status=WaveStatus.CANCELLED)
    )
    await db.flush()
    await db.refresh(campaign)
    return campaign


@router.delete(
    "/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_campaign(
    campaign_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Hard-delete a campaign and its waves/signups/reports.

    FK rows cascade (recruitment_waves, recruitment_signups,
    recruitment_reports all use ``ON DELETE CASCADE`` to campaign_id).
    Linked Announcement rows are NOT deleted — their
    ``recruitment_wave_id`` is nullable and the cascade is SET NULL via the
    wave-side FK, so the announcement history of past sends is preserved.

    Allowed in any state; active/pending campaigns are cancelled in-place
    first so the tick loop won't try to re-fire mid-delete.
    """
    from app.models.announcement import Announcement
    from sqlalchemy import update

    campaign = await _get_campaign(db, tenant.id, campaign_id)
    if campaign.status in (
        CampaignStatus.DRAFT,
        CampaignStatus.AWAITING_APPROVAL,
        CampaignStatus.ACTIVE,
        CampaignStatus.PAUSED,
    ):
        await db.execute(
            RecruitmentWave.__table__.update()
            .where(
                RecruitmentWave.campaign_id == campaign.id,
                RecruitmentWave.status == WaveStatus.PLANNED,
            )
            .values(status=WaveStatus.CANCELLED)
        )
        await db.flush()

    # Detach announcements from this campaign's waves before deletion. The
    # FK was created without ON DELETE SET NULL, so cascading would fail
    # while announcements still reference the waves about to be deleted.
    wave_ids_q = await db.execute(
        select(RecruitmentWave.id).where(
            RecruitmentWave.campaign_id == campaign.id
        )
    )
    wave_ids = [w for w in wave_ids_q.scalars().all()]
    if wave_ids:
        await db.execute(
            update(Announcement)
            .where(Announcement.recruitment_wave_id.in_(wave_ids))
            .values(recruitment_wave_id=None)
        )
        await db.flush()

    await db.delete(campaign)
    await db.flush()


@router.post("/waves/{wave_id}/cancel", response_model=WaveResponse)
async def cancel_wave(
    wave_id: uuid.UUID,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    wave = await db.get(RecruitmentWave, wave_id)
    if not wave or wave.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Wave not found")
    if wave.status != WaveStatus.PLANNED:
        raise HTTPException(
            status_code=400,
            detail="Only planned waves can be cancelled.",
        )
    wave.status = WaveStatus.CANCELLED
    await db.flush()
    await db.refresh(wave)
    return wave


@router.get("/waves/{wave_id}/recipients")
async def get_wave_recipients(
    wave_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    """Return the wave's recipients along with the message that was sent.

    The unrendered SMS template + event_context are persisted on the
    linked ``Announcement`` row (snapshotted at send time so admin edits
    to the campaign templates after the fact don't rewrite history).
    Each recipient's ACTUAL delivered SMS is appended to their
    ``Conversation.message_history`` by ``_append_announcement_to_history``
    — we surface those entries here so the admin sees the per-volunteer
    text exactly as it went out.

    For waves that haven't fired yet (PLANNED / SKIPPED / CANCELLED) the
    targeted list is empty by design — the recruiter only resolves
    recipients at send time.
    """
    from app.agents.recruiter.executor import (
        _render_template,
        _render_with_event_header,
    )
    from app.models.announcement import Announcement
    from app.models.contact import Contact
    from app.models.conversation import Conversation, ConversationStatus
    from app.prompts.conversation import get_announcement_header_template

    wave = await db.get(RecruitmentWave, wave_id)
    if not wave or wave.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Wave not found")

    # Linked Announcement carries the as-sent template + event_context.
    announcement: Announcement | None = None
    template_message: str | None = None
    event_context: dict | None = None
    if wave.announcement_id:
        announcement = await db.get(Announcement, wave.announcement_id)
        if announcement:
            template_message = announcement.message
            event_context = announcement.event_context

    raw_ids = wave.targeted_contact_ids or []
    contact_ids: list[uuid.UUID] = []
    for cid in raw_ids:
        try:
            contact_ids.append(uuid.UUID(str(cid)))
        except (ValueError, TypeError):
            continue

    # Bulk-load contacts in original send order
    by_id: dict[uuid.UUID, Contact] = {}
    if contact_ids:
        rows_q = await db.execute(
            select(Contact).where(
                Contact.tenant_id == tenant.id,
                Contact.id.in_(contact_ids),
            )
        )
        for c in rows_q.scalars().all():
            by_id[c.id] = c

    # Bulk-load matching conversation entries (one query) so we can
    # surface the actually-delivered SMS text per recipient. We pull
    # active 'customer' conversations for the relevant phones and pick
    # the entry whose timestamp is closest to (and within ~5 minutes of)
    # the wave's announcement.sent_at.
    convo_messages_by_phone: dict[str, str] = {}
    if announcement and announcement.sent_at and by_id:
        phones = [c.phone for c in by_id.values() if c.phone]
        if phones:
            convos_q = await db.execute(
                select(Conversation)
                .where(
                    Conversation.tenant_id == tenant.id,
                    Conversation.contact_phone.in_(phones),
                    Conversation.sender_type == "customer",
                )
            )
            sent_at_ts = announcement.sent_at.timestamp()
            for convo in convos_q.scalars().all():
                best_text: str | None = None
                best_delta = 10 * 60  # 10-min window
                for entry in convo.message_history or []:
                    if entry.get("kind") != "announcement":
                        continue
                    raw_ts = entry.get("timestamp")
                    if not raw_ts:
                        continue
                    try:
                        msg_ts = datetime.fromisoformat(
                            raw_ts.replace("Z", "+00:00")
                        ).timestamp()
                    except (ValueError, TypeError):
                        continue
                    delta = abs(msg_ts - sent_at_ts)
                    if delta <= best_delta:
                        best_delta = delta
                        best_text = entry.get("content")
                if best_text:
                    convo_messages_by_phone[convo.contact_phone] = best_text

    # Resolve the header template for fallback re-rendering when an
    # individual conversation entry isn't found.
    header_template: str | None = None
    if announcement and template_message:
        header_template = await get_announcement_header_template(
            db, tenant.id
        )

    recipients: list[dict] = []
    for cid in contact_ids:
        c = by_id.get(cid)
        if not c:
            recipients.append(
                {
                    "contact_id": str(cid),
                    "name": None,
                    "phone": None,
                    "deleted": True,
                    "message": None,
                }
            )
            continue
        # Prefer the actual delivered text from conversation history;
        # fall back to re-rendering the template against this contact
        # so the admin still sees something meaningful even if the
        # conversation entry can't be matched.
        message: str | None = convo_messages_by_phone.get(c.phone)
        if message is None and template_message and header_template is not None:
            body = _render_template(template_message, c, event_context or {})
            message = _render_with_event_header(
                header_template, event_context or {}, body
            )
        recipients.append(
            {
                "contact_id": str(c.id),
                "name": c.name,
                "phone": c.phone,
                "deleted": False,
                "message": message,
            }
        )

    return {
        "wave_id": str(wave.id),
        "wave_number": wave.wave_number,
        "status": wave.status.value,
        "sent_count": wave.sent_count,
        "signups_attributed": wave.signups_attributed,
        "recipient_count": len(recipients),
        "announcement_id": str(announcement.id) if announcement else None,
        "template_message": template_message,
        "event_context": event_context,
        "sent_at": announcement.sent_at.isoformat()
        if announcement and announcement.sent_at
        else None,
        "recipients": recipients,
    }


# ── Read ──


@router.get(
    "/campaigns/{campaign_id}", response_model=CampaignDetailResponse
)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
):
    campaign = await _get_campaign(db, tenant.id, campaign_id)
    waves_q = await db.execute(
        select(RecruitmentWave)
        .where(RecruitmentWave.campaign_id == campaign.id)
        .order_by(RecruitmentWave.scheduled_at)
    )
    waves = list(waves_q.scalars().all())
    reports_q = await db.execute(
        select(RecruitmentReport)
        .where(RecruitmentReport.campaign_id == campaign.id)
        .order_by(desc(RecruitmentReport.report_date))
        .limit(7)
    )
    reports = list(reports_q.scalars().all())

    service_ids = [
        uuid.UUID(g["appointment_type_id"])
        for g in (campaign.goals or [])
        if g.get("appointment_type_id")
    ]
    slot = await db.get(SpecificDateSlot, campaign.event_slot_id)
    signups = (
        await executor.current_signups_per_service(db, slot, service_ids)
        if slot
        else {}
    )

    payload = CampaignDetailResponse.model_validate(campaign)
    payload.waves = [WaveResponse.model_validate(w) for w in waves]
    payload.recent_reports = [
        # ReportSummary works because of from_attributes config
        r for r in reports
    ]
    payload.current_signups = signups
    return payload


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    db: DbSession,
    current_user: CurrentUser,
    tenant: CurrentTenant,
    status_filter: CampaignStatus | None = Query(default=None, alias="status"),
    at_risk_only: bool = Query(default=False),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """Top-level Campaigns page: rows + aggregate stats."""
    # Pull campaigns + their slot dates in one query
    q = (
        select(RecruitmentCampaign, SpecificDateSlot)
        .join(
            SpecificDateSlot,
            SpecificDateSlot.id == RecruitmentCampaign.event_slot_id,
        )
        .where(RecruitmentCampaign.tenant_id == tenant.id)
    )
    if status_filter:
        q = q.where(RecruitmentCampaign.status == status_filter)
    if date_from:
        q = q.where(SpecificDateSlot.date >= date_from)
    if date_to:
        q = q.where(SpecificDateSlot.date <= date_to)
    # Closest-event-first ordering matches the runtime tick priority.
    q = q.order_by(SpecificDateSlot.date.asc())

    rows = list((await db.execute(q)).all())
    total = len(rows)
    page_slice = rows[(page - 1) * page_size : page * page_size]

    # Service-name lookup
    type_ids: set[uuid.UUID] = set()
    for c, _ in rows:
        for g in c.goals or []:
            try:
                type_ids.add(uuid.UUID(g["appointment_type_id"]))
            except (KeyError, ValueError, TypeError):
                continue
    type_names: dict[str, str] = {}
    if type_ids:
        names_q = await db.execute(
            select(AppointmentType.id, AppointmentType.name).where(
                AppointmentType.id.in_(type_ids)
            )
        )
        type_names = {str(tid): name for tid, name in names_q.all()}

    today = date.today()
    items: list[CampaignListItem] = []
    total_needed = 0
    total_signed_up = 0
    at_risk_count = 0
    for c, slot in page_slice:
        signups = await executor.current_signups_per_service(
            db, slot, [uuid.UUID(g["appointment_type_id"]) for g in c.goals or [] if g.get("appointment_type_id")]
        )
        fill_per_service: dict[str, dict] = {}
        c_needed = 0
        c_signed = 0
        for g in c.goals or []:
            sid = g.get("appointment_type_id")
            if not sid:
                continue
            # min_required is canonical; fall back to legacy 'target' and
            # 'min_acceptable' keys so older campaigns still render.
            min_required = (
                g.get("min_required")
                if g.get("min_required") is not None
                else g.get("min_acceptable")
                if g.get("min_acceptable") is not None
                else g.get("target", 0)
            )
            try:
                min_required = int(min_required or 0)
            except (TypeError, ValueError):
                min_required = 0
            max_allowed_raw = g.get("max_allowed")
            try:
                max_allowed = (
                    int(max_allowed_raw) if max_allowed_raw is not None else None
                )
            except (TypeError, ValueError):
                max_allowed = None
            signed = int(signups.get(sid, 0))
            fill_per_service[sid] = {
                "service_name": type_names.get(sid),
                # Keep `target` for backward compat with existing front-end
                # which reads .target; it maps to min_required now.
                "target": min_required,
                "min_required": min_required,
                "max_allowed": max_allowed,
                "signups": signed,
            }
            c_needed += min_required
            c_signed += signed
        overall_pct = (c_signed / c_needed) if c_needed else 0.0
        days_to_event = (slot.date - today).days

        # at-risk: close to event AND under threshold
        at_risk = (
            c.status == CampaignStatus.ACTIVE
            and 0 <= days_to_event <= AT_RISK_DAYS_REMAINING
            and overall_pct < AT_RISK_FILL_PCT_BELOW
        )
        if at_risk:
            at_risk_count += 1
        if at_risk_only and not at_risk:
            continue

        total_needed += c_needed
        total_signed_up += c_signed

        last_sent_q = await db.execute(
            select(func.max(RecruitmentWave.scheduled_at)).where(
                RecruitmentWave.campaign_id == c.id,
                RecruitmentWave.status == WaveStatus.SENT,
            )
        )
        next_due_q = await db.execute(
            select(func.min(RecruitmentWave.scheduled_at)).where(
                RecruitmentWave.campaign_id == c.id,
                RecruitmentWave.status == WaveStatus.PLANNED,
            )
        )
        items.append(
            CampaignListItem(
                id=c.id,
                event_slot_id=slot.id,
                event_label=slot.label,
                event_date=slot.date,
                days_to_event=days_to_event,
                status=c.status,
                fill_per_service=fill_per_service,
                overall_fill_pct=round(overall_pct, 3),
                last_wave_sent_at=last_sent_q.scalar(),
                next_wave_due_at=next_due_q.scalar(),
                at_risk=at_risk,
            )
        )

    # Aggregate stats over ACTIVE campaigns
    active_total = sum(
        1 for c, _ in rows if c.status == CampaignStatus.ACTIVE
    )
    week_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    messaged_7d_q = await db.execute(
        select(func.coalesce(func.sum(RecruitmentWave.sent_count), 0)).where(
            RecruitmentWave.tenant_id == tenant.id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= week_cutoff,
        )
    )
    messaged_7d = int(messaged_7d_q.scalar() or 0)
    aggregate = {
        "active_campaigns": active_total,
        "total_volunteers_needed": total_needed,
        "total_signed_up": total_signed_up,
        "total_messaged_7d": messaged_7d,
        "at_risk_count": at_risk_count,
    }

    return CampaignListResponse(
        items=items, aggregate=aggregate, total=total
    )


async def _get_campaign(
    db, tenant_id: uuid.UUID, campaign_id: uuid.UUID
) -> RecruitmentCampaign:
    campaign = await db.get(RecruitmentCampaign, campaign_id)
    if not campaign or campaign.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign
