"""Phase 3 — service-log helpers.

Engagement-domain utilities for the SWITCH/ALSO volunteer intents
and the APPROVE/REJECT admin commands. Splits cleanly from the
engagement agent's intent module so the SQL + admin notification
plumbing has one home.

Key responsibilities:
  - resolve_service_name(): fuzzy match a service name against
    appointment_types for the booking's tenant + the booking's slot's
    service_config.
  - create_pending_entry(): supersede prior pending rows (decision #17),
    insert the new row, fire admin notification.
  - approve_pending() / reject_pending(): optimistic-version write
    (decision #29b) with stale-error semantics.

Custom exception OptimisticLockError is raised when version mismatch
indicates the row was modified between read and write.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import EVENT_ADMIN_OVERRIDE, AGENT_ENGAGEMENT
from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
from app.models.agent_call_log import AgentCallLog
from app.models.appointment_type import AppointmentType
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking
from app.models.booking_service_log import (
    BSL_SOURCE_VOLUNTEER_SMS,
    BSL_STATUS_APPROVED,
    BSL_STATUS_PENDING,
    BSL_STATUS_REJECTED,
    BSL_STATUS_SUPERSEDED,
    BookingServiceLog,
)
from app.models.contact import Contact
from app.models.notification import AdminNotification, NotificationType

logger = get_logger("service_log")


class OptimisticLockError(Exception):
    """Raised when a status-change UPDATE hits 0 rowcount — meaning
    the row was modified (most often by a supersede) between read and
    write. Caller should respond with 'stale, please retry'.
    """


# ── Service-name resolution ─────────────────────────────────────────


async def resolve_service_name(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    slot: SpecificDateSlot,
    name_query: str,
) -> AppointmentType | None:
    """Fuzzy match a user-typed service name against active appointment
    types for the tenant. Filters by the slot's `service_config` so we
    only return services actually on the slot.
    """
    q = (name_query or "").strip()
    if not q:
        return None

    # Collect appointment_type_ids declared on the slot.
    allowed_ids: set[uuid.UUID] = set()
    for svc in (slot.service_config or []):
        if isinstance(svc, dict) and "appointment_type_id" in svc:
            try:
                allowed_ids.add(uuid.UUID(svc["appointment_type_id"]))
            except (TypeError, ValueError):
                continue

    like = f"%{q}%"
    stmt = select(AppointmentType).where(
        AppointmentType.tenant_id == tenant_id,
        AppointmentType.is_active.is_(True),
        AppointmentType.name.ilike(like),
    )
    if allowed_ids:
        stmt = stmt.where(AppointmentType.id.in_(allowed_ids))
    result = await db.execute(stmt.limit(2))
    rows = list(result.scalars().all())
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        # Prefer exact case-insensitive match if present
        for r in rows:
            if (r.name or "").lower() == q.lower():
                return r
        return None
    return None


# ── Admin notification dispatch ────────────────────────────────────


async def _notify_admins_of_pending(
    db: AsyncSession,
    *,
    entry: BookingServiceLog,
    booking: Booking,
    slot: SpecificDateSlot,
    appointment_type: AppointmentType,
    contact: Contact,
    is_switch: bool,
    prior_service_name: str | None,
) -> None:
    """In-app notification + SMS to every admin in receiving roles.

    Uses prompt_admin_service_approval_request template. Same SMS
    pattern as the Phase 2 roster pings (best-effort SMS, in-app row
    always recorded so the bell icon picks it up).
    """
    from app.prompts.conversation import _get_prompt, PROMPT_KEYS
    from app.services.sms import send_sms

    # Receiving admins: OWNER + MANAGER + STAFF, active. We intentionally
    # don't filter on status_pings_opted_out — Phase 2 opt-outs are
    # specific to the auto-ping schedule, not approval requests.
    admins_result = await db.execute(
        select(AdminUser).where(
            AdminUser.tenant_id == booking.tenant_id,
            AdminUser.is_active.is_(True),
            AdminUser.role.in_(
                [AdminRole.OWNER, AdminRole.MANAGER, AdminRole.STAFF]
            ),
        )
    )
    admins = list(admins_result.scalars().all())
    if not admins:
        return

    template = await _get_prompt(
        db,
        "prompt_admin_service_approval_request",
        PROMPT_KEYS["prompt_admin_service_approval_request"],
        tenant_id=booking.tenant_id,
    )
    body = template.format(
        volunteer_name=contact.name or contact.phone,
        event_name=slot.label or "(unnamed event)",
        from_service=prior_service_name or "(unassigned)",
        to_service=appointment_type.name,
        link=f"/run-sheet/{slot.id}",
    )

    # Send the same body to every admin via in-app + SMS (best-effort).
    from app.models.tenant import Tenant

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == booking.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    for admin in admins:
        # In-app
        db.add(
            AdminNotification(
                tenant_id=booking.tenant_id,
                admin_user_id=admin.id,
                type=NotificationType.SERVICE_APPROVAL_REQUEST,
                title=(
                    f"{'Switch' if is_switch else 'Add'} request: "
                    f"{contact.name or contact.phone}"
                ),
                body=body,
                reference_id=entry.id,
                reference_type="booking_service_log",
            )
        )
        # SMS — only if admin has a phone
        if admin.phone:
            try:
                await send_sms(to=admin.phone, body=body, tenant=tenant)
            except Exception:
                logger.exception(
                    "Failed to send service-approval SMS to admin=%s",
                    admin.id,
                )


# ── Entry creation (SWITCH / ALSO) ──────────────────────────────────


async def create_pending_entry(
    db: AsyncSession,
    *,
    booking: Booking,
    slot: SpecificDateSlot,
    appointment_type: AppointmentType,
    contact: Contact,
    is_switch: bool,
) -> BookingServiceLog:
    """Insert a new pending row. For SWITCH: supersede any prior pending
    rows on this booking (decision #17). For ALSO: leave priors alone.

    Returns the newly-inserted row.
    """
    now_utc = datetime.now(timezone.utc)
    prior_service_name: str | None = None

    if is_switch:
        # Find any pending rows on this booking. Mark them superseded,
        # bumping version atomically. We don't include a version
        # predicate here — supersede is itself "always wins" semantics.
        prior_result = await db.execute(
            select(BookingServiceLog, AppointmentType)
            .join(
                AppointmentType,
                BookingServiceLog.appointment_type_id == AppointmentType.id,
            )
            .where(
                BookingServiceLog.booking_id == booking.id,
                BookingServiceLog.status == BSL_STATUS_PENDING,
            )
            .order_by(BookingServiceLog.created_at.desc())
        )
        for prior, prior_appt in prior_result.all():
            prior.status = BSL_STATUS_SUPERSEDED
            prior.version = (prior.version or 0) + 1
            if prior.ended_at is None:
                prior.ended_at = now_utc
            if prior_service_name is None:
                prior_service_name = prior_appt.name

    entry = BookingServiceLog(
        tenant_id=booking.tenant_id,
        booking_id=booking.id,
        appointment_type_id=appointment_type.id,
        started_at=now_utc,
        ended_at=None,
        source=BSL_SOURCE_VOLUNTEER_SMS,
        status=BSL_STATUS_PENDING,
        version=0,
    )
    db.add(entry)
    await db.flush()

    await _notify_admins_of_pending(
        db,
        entry=entry,
        booking=booking,
        slot=slot,
        appointment_type=appointment_type,
        contact=contact,
        is_switch=is_switch,
        prior_service_name=prior_service_name,
    )
    return entry


# ── APPROVE / REJECT (optimistic version) ───────────────────────────


async def approve_pending(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    expected_version: int,
    admin: AdminUser,
) -> BookingServiceLog:
    """Approve a pending entry. Raises OptimisticLockError if version
    has changed (likely supersede race).
    """
    now_utc = datetime.now(timezone.utc)
    result = await db.execute(
        update(BookingServiceLog)
        .where(
            BookingServiceLog.id == entry_id,
            BookingServiceLog.version == expected_version,
            BookingServiceLog.status == BSL_STATUS_PENDING,
        )
        .values(
            status=BSL_STATUS_APPROVED,
            version=expected_version + 1,
            approved_at=now_utc,
            approved_by_admin_id=admin.id,
        )
    )
    if (result.rowcount or 0) == 0:
        raise OptimisticLockError(
            f"booking_service_log {entry_id} stale; expected_version={expected_version}"
        )

    # Audit log row.
    db.add(
        AgentCallLog(
            tenant_id=admin.tenant_id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_ADMIN_OVERRIDE,
            source=AGENT_ENGAGEMENT,
            destination=AGENT_ENGAGEMENT,
            decision_reason="service_log_approved",
            payload={
                "target_table": "booking_service_log",
                "target_id": str(entry_id),
                "field": "status",
                "prior_value": BSL_STATUS_PENDING,
                "new_value": BSL_STATUS_APPROVED,
                "admin_user_id": str(admin.id),
            },
        )
    )

    # Evict Live Events cache so the pending count drops.
    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(admin.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    await db.flush()

    # Re-fetch for return.
    refreshed = await db.execute(
        select(BookingServiceLog).where(BookingServiceLog.id == entry_id)
    )
    return refreshed.scalar_one()


async def reject_pending(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    expected_version: int,
    admin: AdminUser,
    reason: str | None = None,
) -> BookingServiceLog:
    """Reject a pending entry. Raises OptimisticLockError on race."""
    result = await db.execute(
        update(BookingServiceLog)
        .where(
            BookingServiceLog.id == entry_id,
            BookingServiceLog.version == expected_version,
            BookingServiceLog.status == BSL_STATUS_PENDING,
        )
        .values(
            status=BSL_STATUS_REJECTED,
            version=expected_version + 1,
            approved_at=datetime.now(timezone.utc),
            approved_by_admin_id=admin.id,
            notes=reason,
        )
    )
    if (result.rowcount or 0) == 0:
        raise OptimisticLockError(
            f"booking_service_log {entry_id} stale; expected_version={expected_version}"
        )

    db.add(
        AgentCallLog(
            tenant_id=admin.tenant_id,
            conversation_id=None,
            turn_id=uuid.uuid4(),
            event_type=EVENT_ADMIN_OVERRIDE,
            source=AGENT_ENGAGEMENT,
            destination=AGENT_ENGAGEMENT,
            decision_reason="service_log_rejected",
            payload={
                "target_table": "booking_service_log",
                "target_id": str(entry_id),
                "field": "status",
                "prior_value": BSL_STATUS_PENDING,
                "new_value": BSL_STATUS_REJECTED,
                "admin_user_id": str(admin.id),
                "reason": reason,
            },
        )
    )

    try:
        from app.agents.orchestrator.admin_prompt_blocks import (
            evict_live_events_cache,
        )
        evict_live_events_cache(admin.tenant_id)
    except ImportError:  # pragma: no cover
        pass

    await db.flush()
    refreshed = await db.execute(
        select(BookingServiceLog).where(BookingServiceLog.id == entry_id)
    )
    return refreshed.scalar_one()


async def find_latest_pending_for_volunteer_name(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name_query: str,
) -> tuple[BookingServiceLog, Contact, SpecificDateSlot, AppointmentType] | None:
    """Used by APPROVE <name> / REJECT <name> admin SMS commands.

    Returns the latest pending service_log row matching a volunteer
    name in this tenant, or None.
    """
    q = (name_query or "").strip()
    if not q:
        return None
    like = f"%{q}%"
    result = await db.execute(
        select(
            BookingServiceLog, Contact, SpecificDateSlot, AppointmentType
        )
        .join(Booking, BookingServiceLog.booking_id == Booking.id)
        .join(Contact, Booking.contact_id == Contact.id)
        .join(SpecificDateSlot, Booking.event_slot_id == SpecificDateSlot.id)
        .join(
            AppointmentType,
            BookingServiceLog.appointment_type_id == AppointmentType.id,
        )
        .where(
            BookingServiceLog.tenant_id == tenant_id,
            BookingServiceLog.status == BSL_STATUS_PENDING,
            Contact.name.ilike(like),
        )
        .order_by(BookingServiceLog.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    return row
