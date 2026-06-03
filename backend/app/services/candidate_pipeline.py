"""Row 4 / Row 5 — unknown-phone candidate capture.

When an unknown phone texts the webhook, we DO NOT auto-create a
Contact (which would pollute the volunteer roster with anonymous
UNCONTACTED stubs). Instead the inbound signal lands in
`volunteer_candidate` and admin acts on it via the /candidates page.

Decisions:
  - Row 4: when message matches HERE intent AND a live event has
    capacity → fire admin notification (rate-limited 24h per phone).
  - Row 5: silent capture; no notification, no SMS reply.
  - #29(c): predicate-narrow DELETE on prune is race-safe against
    concurrent Invite/Dismiss.
  - #32: 1-year retention cap on terminal-state rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.keywords import CHECKIN_INTENT_REGEX
from app.core.logging import get_logger
from app.models.availability import SpecificDateSlot
from app.models.notification import AdminNotification, NotificationType
from app.models.volunteer_candidate import (
    CANDIDATE_STATUS_NEW,
    VolunteerCandidate,
)
from app.services.event_eligibility import find_live_slot_with_capacity

logger = get_logger("candidate_pipeline")


async def upsert_walkup_candidate(
    db: AsyncSession,
    *,
    phone: str,
    message_body: str,
    tenant_id: uuid.UUID,
    slot_id: uuid.UUID | None,
) -> VolunteerCandidate:
    """Insert-or-update a volunteer_candidate row.

    On first sight: insert with occurrence_count=1.
    On subsequent: increment occurrence_count, update last_seen_at and
    last_message_body. Preserve invited_at / dismissed_at — they don't
    reset just because the phone texted again.

    Idempotent on (tenant_id, phone) via the existing UNIQUE constraint.
    """
    # Try insert; on conflict, do nothing and we'll UPDATE separately.
    # (Two-step approach for clarity; could be a single ON CONFLICT DO UPDATE.)
    truncated = (message_body or "")[:500]  # cap to keep PII surface bounded

    stmt = (
        pg_insert(VolunteerCandidate.__table__)
        .values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            phone=phone,
            occurrence_count=1,
            last_signal_slot_id=slot_id,
            last_message_body=truncated,
            status=CANDIDATE_STATUS_NEW,
        )
        .on_conflict_do_update(
            constraint="uq_candidate_tenant_phone",
            set_={
                "last_seen_at": datetime.now(timezone.utc),
                "occurrence_count": VolunteerCandidate.__table__.c.occurrence_count + 1,
                "last_signal_slot_id": slot_id,
                "last_message_body": truncated,
            },
        )
        .returning(VolunteerCandidate)
    )
    result = await db.execute(stmt)
    candidate = result.scalar_one()
    await db.flush()
    return candidate


async def maybe_notify_walkup_candidate(
    db: AsyncSession,
    *,
    candidate: VolunteerCandidate,
    slot: SpecificDateSlot | None,
) -> None:
    """Fire admin notification if rate-limit not exceeded.

    Row 4 trigger: ANY message matched check-in intent AND a live event
    with capacity exists.

    Rate limit: 1 notification per (tenant, phone) per 24h. We check
    candidate.last_notified_at; if it's within the last 24h, skip.
    """
    if slot is None:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    if (
        candidate.last_notified_at is not None
        and candidate.last_notified_at > cutoff
    ):
        return

    # Render notification body via the prompt template.
    from app.prompts.conversation import _get_prompt, PROMPT_KEYS

    template = await _get_prompt(
        db,
        "prompt_admin_walkup_candidate_notification",
        PROMPT_KEYS["prompt_admin_walkup_candidate_notification"],
        tenant_id=candidate.tenant_id,
    )
    body = template.format(
        phone=candidate.phone,
        event_name=slot.label or "(unnamed event)",
        link=f"/candidates/{candidate.id}",
    )

    db.add(
        AdminNotification(
            tenant_id=candidate.tenant_id,
            type=NotificationType.WALKUP_CANDIDATE,
            title="Walk-up candidate",
            body=body,
            reference_id=candidate.id,
            reference_type="volunteer_candidate",
        )
    )

    # Atomically stamp last_notified_at so the rate-limit holds across
    # concurrent inbounds.
    candidate.last_notified_at = datetime.now(timezone.utc)
    await db.flush()


async def handle_unknown_phone_inbound(
    db: AsyncSession,
    *,
    phone: str,
    message_body: str,
    tenant_id: uuid.UUID,
) -> bool:
    """Pipeline branch for unknown-phone inbound (Row 4 / Row 5 combined).

    Returns True if the candidate path was taken (caller should NOT
    fall through to existing _get_or_create_contact / consent flow).
    Returns False only if tenant_id is None (paranoid guard); the
    canonical case always returns True.

    Behavior matches the locked pseudocode (review-pass A2 + #1):
      - Always create/update a volunteer_candidate row.
      - Fire admin notification ONLY when intent + live event match (Row 4).
      - Always return silently — no SMS reply to the unknown phone.
    """
    if tenant_id is None:
        return False

    # Phase 1 step 5b: cheap regex check (no engagement-agent imports).
    intent_matches = bool(CHECKIN_INTENT_REGEX.search(message_body or ""))
    live_slot = await find_live_slot_with_capacity(db, tenant_id) if intent_matches else None
    slot_id = live_slot.id if live_slot is not None else None

    candidate = await upsert_walkup_candidate(
        db,
        phone=phone,
        message_body=message_body,
        tenant_id=tenant_id,
        slot_id=slot_id,
    )

    if intent_matches and live_slot is not None:
        await maybe_notify_walkup_candidate(db, candidate=candidate, slot=live_slot)

    return True
