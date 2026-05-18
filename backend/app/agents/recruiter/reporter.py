"""Daily SMS report generator for the Recruitment Agent.

LLM seam #2 of the two-seam design. Once per day per active campaign:
- Aggregate fill snapshot, recent wave activity, attributed signups.
- Make one short Anthropic call for a 2–3 sentence narrative.
- Send the report via SMS to the campaign's creating admin's phone
  (locked decision #2) and mirror into the admin's
  ``sender_type='admin'`` conversation history so it appears in the
  test-conversation view.
- Persist a ``RecruitmentReport`` row for the dashboard's Reports tab.

Failures here are non-fatal — a failed report should never crash the
scheduler job for other campaigns.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.recruiter import executor
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.admin_user import AdminUser
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentReport,
    RecruitmentSignup,
    RecruitmentWave,
    ReportChannel,
    WaveStatus,
)
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsageSource
from app.agents.recruiter.planner import _get_ai_model as get_ai_model
from app.modules.tool_executor import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    DEFAULT_MODEL,
)
from app.services.sms import send_sms
from app.services.token_usage import record_token_usage

logger = get_logger("recruiter.reporter")

REPORTER_SYSTEM_PROMPT = """\
You are writing a 2–3 sentence daily SMS update for an admin who is using a \
volunteer recruitment agent to staff an event. Use ONLY the numbers in the \
payload — do not invent. Keep the entire message under 300 characters so it \
fits in one SMS. Lead with how the event is tracking (X% filled, services \
short by N), mention the most recent wave activity, and finish with the \
next action if anything is due. Be plain and concrete; do not use emojis or \
marketing language.
"""


async def _build_report_payload(
    db: AsyncSession,
    campaign: RecruitmentCampaign,
    slot: SpecificDateSlot,
) -> dict:
    """Compute the numeric snapshot the LLM will narrate."""
    service_ids = [
        uuid.UUID(g["appointment_type_id"])
        for g in campaign.goals or []
        if g.get("appointment_type_id")
    ]
    signups = await executor.current_signups_per_service(
        db, slot, service_ids
    )

    # Service names
    type_q = await db.execute(
        select(AppointmentType.id, AppointmentType.name).where(
            AppointmentType.id.in_(service_ids)
        )
    )
    type_names = {str(tid): name for tid, name in type_q.all()}

    # Per-service fill
    per_service: list[dict] = []
    total_target = 0
    total_signed = 0
    for g in campaign.goals or []:
        sid = g.get("appointment_type_id")
        if not sid:
            continue
        target = int(g.get("target", 0))
        signed = int(signups.get(sid, 0))
        total_target += target
        total_signed += signed
        per_service.append(
            {
                "service": type_names.get(sid, sid[:8]),
                "target": target,
                "signups": signed,
                "gap": max(0, target - signed),
            }
        )

    yesterday_cutoff = datetime.now(timezone.utc) - timedelta(days=1)

    # Waves sent in the last 24h
    recent_waves_q = await db.execute(
        select(func.count(RecruitmentWave.id)).where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= yesterday_cutoff,
        )
    )
    waves_24h = int(recent_waves_q.scalar() or 0)

    messaged_24h_q = await db.execute(
        select(func.coalesce(func.sum(RecruitmentWave.sent_count), 0)).where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.SENT,
            RecruitmentWave.scheduled_at >= yesterday_cutoff,
        )
    )
    messaged_24h = int(messaged_24h_q.scalar() or 0)

    signups_24h_q = await db.execute(
        select(func.count(RecruitmentSignup.id)).where(
            RecruitmentSignup.campaign_id == campaign.id,
            RecruitmentSignup.attributed_at >= yesterday_cutoff,
        )
    )
    signups_24h = int(signups_24h_q.scalar() or 0)

    next_wave_q = await db.execute(
        select(func.min(RecruitmentWave.scheduled_at)).where(
            RecruitmentWave.campaign_id == campaign.id,
            RecruitmentWave.status == WaveStatus.PLANNED,
        )
    )
    next_wave_at = next_wave_q.scalar()

    days_to_event = (slot.date - date.today()).days

    overall_pct = (total_signed / total_target) if total_target else 0.0

    return {
        "event_label": slot.label or "event",
        "event_date": slot.date.isoformat(),
        "days_to_event": days_to_event,
        "overall_target": total_target,
        "overall_signed_up": total_signed,
        "overall_fill_pct": round(overall_pct, 3),
        "per_service": per_service,
        "waves_sent_24h": waves_24h,
        "contacts_messaged_24h": messaged_24h,
        "signups_attributed_24h": signups_24h,
        "next_wave_at": next_wave_at.isoformat() if next_wave_at else None,
    }


async def _generate_narrative(
    payload: dict, tenant: Tenant, api_key: str, model: str
) -> tuple[str, int, int]:
    """One short Anthropic call. Returns (text, input_tokens, output_tokens)."""
    user_message = (
        "Write the SMS update for this campaign payload:\n"
        + json.dumps(payload, default=str)
    )
    body = {
        "model": model,
        "max_tokens": 200,
        "system": REPORTER_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    # Rate-limit guard (see design_decisions.md #15). Reporter is one call.
    from app.services.llm_rate_limit import (
        consume,
        get_tenant_limit,
        LLMRateLimitExceeded,
    )
    try:
        # Reporter doesn't have a db handle here; open a brief one.
        from app.core.database import async_session_factory as _sf
        async with _sf() as _db:
            tenant_limit = await get_tenant_limit(_db, tenant.id)
        await consume(tenant.id, limit=tenant_limit)
    except LLMRateLimitExceeded:
        # Fall back to deterministic narrative without spending budget.
        return (_fallback_narrative(payload), 0, 0)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            ANTHROPIC_API_URL, json=body, headers=headers, timeout=20.0
        )
    if response.status_code != 200:
        logger.error(
            "Reporter Anthropic API error %d: %s",
            response.status_code, response.text[:200],
        )
        # Deterministic fallback narrative
        return (_fallback_narrative(payload), 0, 0)
    data = response.json()
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    usage = data.get("usage", {})
    return (
        text.strip() or _fallback_narrative(payload),
        int(usage.get("input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
    )


def _fallback_narrative(payload: dict) -> str:
    pct = int(round(payload.get("overall_fill_pct", 0) * 100))
    return (
        f"{payload.get('event_label')} on {payload.get('event_date')}: "
        f"{pct}% filled "
        f"({payload.get('overall_signed_up')}/{payload.get('overall_target')}). "
        f"{payload.get('contacts_messaged_24h', 0)} contacted in the last 24h, "
        f"{payload.get('signups_attributed_24h', 0)} new signups."
    )


async def _report_one_campaign(
    db: AsyncSession,
    tenant: Tenant,
    campaign: RecruitmentCampaign,
    slot: SpecificDateSlot,
) -> None:
    today = date.today()
    # Idempotency guard: don't send two reports for the same day.
    existing_q = await db.execute(
        select(RecruitmentReport).where(
            RecruitmentReport.campaign_id == campaign.id,
            RecruitmentReport.report_date == today,
        )
    )
    if existing_q.scalar_one_or_none():
        return

    payload = await _build_report_payload(db, campaign, slot)

    # Resolve admin phone
    admin = await db.get(AdminUser, campaign.created_by_admin_id)
    admin_phone = admin.phone if admin and admin.phone else None

    model = await get_ai_model(db, tenant)
    api_key = tenant.anthropic_api_key or settings.anthropic_api_key
    narrative, in_tok, out_tok = await _generate_narrative(
        payload, tenant, api_key, model
    )

    delivered = False
    if admin_phone:
        try:
            ok = await send_sms(admin_phone, narrative, tenant)
            if ok:
                delivered = True
                await executor._append_to_admin_conversation(
                    db, tenant.id, admin_phone, narrative
                )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to send daily report SMS: campaign=%s", campaign.id
            )

    report = RecruitmentReport(
        tenant_id=tenant.id,
        campaign_id=campaign.id,
        report_date=today,
        payload=payload,
        narrative=narrative,
        sent_via=ReportChannel.SMS if delivered else ReportChannel.NONE,
        delivered_at=datetime.now(timezone.utc) if delivered else None,
    )
    db.add(report)
    await db.flush()

    if in_tok or out_tok:
        try:
            await record_token_usage(
                db=db,
                tenant_id=tenant.id,
                source=TokenUsageSource.CONVERSATION,
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                contact_id=None,
                contact_phone=None,
                tool_calls=None,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to record reporter token usage")


async def daily_report_run() -> None:
    """Entry point for the scheduler job.

    Iterates active tenants → active/paused campaigns. Each campaign gets
    its own report. Failures isolated per-campaign.
    """
    async with async_session_factory() as db:
        try:
            tenants_q = await db.execute(
                select(Tenant).where(Tenant.is_active.is_(True))
            )
            tenants = list(tenants_q.scalars().all())

            for tenant in tenants:
                campaigns_q = await db.execute(
                    select(RecruitmentCampaign, SpecificDateSlot)
                    .join(
                        SpecificDateSlot,
                        SpecificDateSlot.id
                        == RecruitmentCampaign.event_slot_id,
                    )
                    .where(
                        RecruitmentCampaign.tenant_id == tenant.id,
                        RecruitmentCampaign.status.in_(
                            [CampaignStatus.ACTIVE, CampaignStatus.PAUSED]
                        ),
                    )
                )
                rows = list(campaigns_q.all())
                for campaign, slot in rows:
                    try:
                        await _report_one_campaign(db, tenant, campaign, slot)
                    except Exception as e:  # noqa: BLE001
                        logger.exception(
                            "Daily report failed for campaign %s: %s",
                            campaign.id, e,
                        )

            await db.commit()
        except Exception as e:  # noqa: BLE001
            await db.rollback()
            logger.error(
                "recruitment_daily_report failed: %s", e, exc_info=True
            )


__all__ = ["daily_report_run"]
