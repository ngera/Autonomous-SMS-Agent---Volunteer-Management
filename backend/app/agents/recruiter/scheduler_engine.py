"""Pure state-machine that decides the next action for a recruitment campaign.

Inputs are the campaign + its waves + the current fill snapshot (a small dict
the caller computes once). All decisions are deterministic; no I/O happens
here so this is trivially unit-testable.

The outer tick loop is responsible for closest-event-first ordering across
campaigns AND for computing which services are still in min-phase across
all competing campaigns in the tenant. This module reasons about ONE
campaign at a time, given those inputs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Literal

from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)


Phase = Literal["min", "max"]


class ActionKind(str, Enum):
    NOOP = "noop"               # nothing to do this tick
    SEND_WAVE = "send_wave"     # fire a specific wave that is due
    COMPLETE = "complete"       # all services filled; mark campaign completed
    ESCALATE = "escalate"       # exhaustion / no eligible recipients
    ABANDON = "abandon"         # event date has passed without fill


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    wave_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    phase: Phase = "min"
    reason: str = ""


@dataclass(frozen=True)
class FillSnapshot:
    """Current signups per service for the event.

    Caller passes ``per_service`` as a dict keyed by appointment_type_id (str
    or UUID) → current signup count. ``targets`` is read from campaign.goals.
    """
    per_service: dict[str, int]


def _coerce_int(val: object, fallback: int = 0) -> int:
    try:
        return int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _min_map(campaign: RecruitmentCampaign) -> dict[str, int]:
    """service_id -> min_required (accepts legacy 'target' / 'min_acceptable')."""
    out: dict[str, int] = {}
    for goal in campaign.goals or []:
        sid = goal.get("appointment_type_id")
        if not sid:
            continue
        val = (
            goal.get("min_required")
            if goal.get("min_required") is not None
            else goal.get("min_acceptable")
            if goal.get("min_acceptable") is not None
            else goal.get("target", 0)
        )
        out[str(sid)] = _coerce_int(val, 0)
    return out


def _max_map(campaign: RecruitmentCampaign) -> dict[str, int | None]:
    """service_id -> max_allowed (None means no upper bound beyond min)."""
    out: dict[str, int | None] = {}
    for goal in campaign.goals or []:
        sid = goal.get("appointment_type_id")
        if not sid:
            continue
        m = goal.get("max_allowed")
        out[str(sid)] = _coerce_int(m, 0) if m is not None else None
    return out


def _target_for_phase(
    service_id: uuid.UUID,
    min_map: dict[str, int],
    max_map: dict[str, int | None],
    phase: Phase,
) -> int:
    key = str(service_id)
    if phase == "max":
        m = max_map.get(key)
        if m is not None:
            return m
    return min_map.get(key, 0)


def _gap_for_service(
    service_id: uuid.UUID,
    targets: dict[str, int],
    fill: FillSnapshot,
) -> int:
    target = targets.get(str(service_id), 0)
    current = fill.per_service.get(str(service_id), 0)
    return max(0, target - current)


def _shortfall_ratio(
    service_id: uuid.UUID,
    targets: dict[str, int],
    fill: FillSnapshot,
) -> float:
    target = targets.get(str(service_id), 0)
    if target <= 0:
        return 0.0
    return _gap_for_service(service_id, targets, fill) / target


def _all_min_filled(
    min_map: dict[str, int], fill: FillSnapshot
) -> bool:
    if not min_map:
        return False
    for sid, target in min_map.items():
        if fill.per_service.get(sid, 0) < target:
            return False
    return True


def _all_targets_filled(
    min_map: dict[str, int],
    max_map: dict[str, int | None],
    fill: FillSnapshot,
) -> bool:
    """Campaign is complete when every service is at max_allowed (if set)
    or at min_required (if no max defined)."""
    if not min_map:
        return False
    for sid in min_map:
        ceiling = max_map.get(sid)
        target = ceiling if ceiling is not None else min_map[sid]
        if fill.per_service.get(sid, 0) < target:
            return False
    return True


def _due_planned_waves(
    waves: Iterable[RecruitmentWave], now: datetime
) -> list[RecruitmentWave]:
    """Return waves currently in PLANNED state whose scheduled_at has passed.

    Ordered by scheduled_at ascending — oldest-overdue first.
    """
    due: list[RecruitmentWave] = []
    for w in waves:
        if w.status != WaveStatus.PLANNED:
            continue
        if w.scheduled_at <= now:
            due.append(w)
    due.sort(key=lambda w: w.scheduled_at)
    return due


def next_action(
    campaign: RecruitmentCampaign,
    waves: list[RecruitmentWave],
    fill: FillSnapshot,
    event_date: datetime,
    *,
    now: datetime | None = None,
    min_phase_service_ids: set[str] | None = None,
) -> Action:
    """Decide the next action for one campaign.

    ``min_phase_service_ids`` is a set of service-id strings (across the
    tenant's whole portfolio of active campaigns) that are still below
    ``min_required`` somewhere. When a wave's service is in this set, the
    fire targets ``min_required``; otherwise it targets ``max_allowed`` if
    set. The tick loop computes this set once per tick.

    Order of evaluation:
      1. Campaign in a terminal state → NOOP
      2. Campaign paused / not active → NOOP
      3. Event date passed → ABANDON if min not met, COMPLETE otherwise
      4. All service targets (max if set, else min) filled → COMPLETE
      5. A planned wave is due → SEND_WAVE — prefer min-phase services
         globally, then max-phase, picking the one with the largest
         shortfall ratio
      6. Otherwise → NOOP
    """
    now = now or datetime.now(timezone.utc)
    min_phase_set: set[str] = (
        set(min_phase_service_ids) if min_phase_service_ids else set()
    )

    if campaign.status in (
        CampaignStatus.COMPLETED,
        CampaignStatus.CANCELLED,
        CampaignStatus.FAILED,
    ):
        return Action(
            kind=ActionKind.NOOP,
            reason=f"Campaign in terminal status {campaign.status.value}",
        )

    if campaign.status != CampaignStatus.ACTIVE:
        return Action(
            kind=ActionKind.NOOP,
            reason=f"Campaign not active ({campaign.status.value})",
        )

    min_map = _min_map(campaign)
    max_map = _max_map(campaign)

    if event_date <= now:
        if _all_min_filled(min_map, fill):
            return Action(
                kind=ActionKind.COMPLETE,
                reason="Event date passed and min staffing met.",
            )
        return Action(
            kind=ActionKind.ABANDON,
            reason="Event date passed without meeting min staffing.",
        )

    if _all_targets_filled(min_map, max_map, fill):
        return Action(
            kind=ActionKind.COMPLETE,
            reason="All service targets met (max or min).",
        )

    due = _due_planned_waves(waves, now)
    if not due:
        return Action(kind=ActionKind.NOOP, reason="No waves due yet.")

    # Classify each due wave by the phase it would fire in. Min phase wins
    # over max — a wave whose service is still below min anywhere in the
    # tenant gets priority over any max-phase wave in this campaign.
    def phase_for(service_id: uuid.UUID) -> Phase:
        return "min" if str(service_id) in min_phase_set else "max"

    def shortfall_at_phase(w: RecruitmentWave) -> tuple[int, float]:
        # Returns (-phase_rank, -ratio) for sort. phase_rank: min=2, max=1.
        phase = phase_for(w.appointment_type_id)
        target_for = {
            sid: _target_for_phase(uuid.UUID(sid), min_map, max_map, phase)
            for sid in min_map.keys()
        }
        ratio = _shortfall_ratio(w.appointment_type_id, target_for, fill)
        phase_rank = 2 if phase == "min" else 1
        return (-phase_rank, -ratio)

    def sort_key(w: RecruitmentWave) -> tuple:
        ph_rank, neg_ratio = shortfall_at_phase(w)
        return (ph_rank, neg_ratio, w.wave_number, w.scheduled_at)

    chosen = sorted(due, key=sort_key)[0]
    phase = phase_for(chosen.appointment_type_id)
    target_now = _target_for_phase(
        chosen.appointment_type_id, min_map, max_map, phase
    )
    current = fill.per_service.get(str(chosen.appointment_type_id), 0)
    if current >= target_now:
        # Wave is due but its phase target is already met. Executor will
        # mark SKIPPED — still return SEND_WAVE so it gets resolved.
        return Action(
            kind=ActionKind.SEND_WAVE,
            wave_id=chosen.id,
            service_id=chosen.appointment_type_id,
            phase=phase,
            reason=(
                f"Wave due but service already at {phase} target "
                f"({current}/{target_now}); executor will skip."
            ),
        )
    return Action(
        kind=ActionKind.SEND_WAVE,
        wave_id=chosen.id,
        service_id=chosen.appointment_type_id,
        phase=phase,
        reason=(
            f"Wave {chosen.wave_number} due, {phase}-phase, current "
            f"{current}/{target_now}."
        ),
    )


def sort_campaigns_closest_event_first(
    campaigns_with_event_dates: list[tuple[RecruitmentCampaign, datetime]],
) -> list[RecruitmentCampaign]:
    """Tick-loop helper: ascending order of event date (closest first).

    Locked decision #5. Returns just the campaigns in order.
    """
    sorted_pairs = sorted(campaigns_with_event_dates, key=lambda p: p[1])
    return [c for c, _ in sorted_pairs]
