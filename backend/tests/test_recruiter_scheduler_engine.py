"""Unit tests for the pure scheduler_engine state machine."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.agents.recruiter import scheduler_engine as se
from app.models.recruitment_campaign import (
    CampaignStatus,
    RecruitmentCampaign,
    RecruitmentWave,
    WaveStatus,
)


def _campaign(status=CampaignStatus.ACTIVE, goals=None):
    c = MagicMock(spec=RecruitmentCampaign)
    c.id = uuid.uuid4()
    c.tenant_id = uuid.uuid4()
    c.status = status
    c.goals = goals or []
    return c


def _wave(
    service_id,
    wave_number=1,
    scheduled_at=None,
    status=WaveStatus.PLANNED,
):
    w = MagicMock(spec=RecruitmentWave)
    w.id = uuid.uuid4()
    w.appointment_type_id = service_id
    w.wave_number = wave_number
    w.scheduled_at = scheduled_at or datetime.now(timezone.utc)
    w.status = status
    return w


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _future_event(days: int = 7) -> datetime:
    return _now() + timedelta(days=days)


# ── terminal states ──


def test_completed_campaign_noop():
    c = _campaign(status=CampaignStatus.COMPLETED)
    action = se.next_action(c, [], se.FillSnapshot({}), _future_event())
    assert action.kind == se.ActionKind.NOOP


def test_cancelled_campaign_noop():
    c = _campaign(status=CampaignStatus.CANCELLED)
    action = se.next_action(c, [], se.FillSnapshot({}), _future_event())
    assert action.kind == se.ActionKind.NOOP


def test_paused_campaign_noop():
    c = _campaign(status=CampaignStatus.PAUSED)
    action = se.next_action(c, [], se.FillSnapshot({}), _future_event())
    assert action.kind == se.ActionKind.NOOP


def test_awaiting_approval_noop():
    c = _campaign(status=CampaignStatus.AWAITING_APPROVAL)
    action = se.next_action(c, [], se.FillSnapshot({}), _future_event())
    assert action.kind == se.ActionKind.NOOP


# ── event date logic ──


def test_event_passed_unfilled_abandons():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "min_required": 5}],
    )
    past_event = _now() - timedelta(hours=1)
    action = se.next_action(c, [], se.FillSnapshot({str(svc): 2}), past_event)
    assert action.kind == se.ActionKind.ABANDON


def test_event_passed_filled_completes():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "min_required": 5}],
    )
    past_event = _now() - timedelta(hours=1)
    action = se.next_action(c, [], se.FillSnapshot({str(svc): 5}), past_event)
    assert action.kind == se.ActionKind.COMPLETE


# ── fill detection (min only) ──


def test_all_services_filled_completes_when_no_max_set():
    svc1 = uuid.uuid4()
    svc2 = uuid.uuid4()
    c = _campaign(
        goals=[
            {"appointment_type_id": str(svc1), "min_required": 3},
            {"appointment_type_id": str(svc2), "min_required": 5},
        ]
    )
    fill = se.FillSnapshot({str(svc1): 3, str(svc2): 5})
    action = se.next_action(c, [], fill, _future_event())
    assert action.kind == se.ActionKind.COMPLETE


def test_overfill_also_completes():
    svc = uuid.uuid4()
    c = _campaign(goals=[{"appointment_type_id": str(svc), "min_required": 3}])
    fill = se.FillSnapshot({str(svc): 7})
    action = se.next_action(c, [], fill, _future_event())
    assert action.kind == se.ActionKind.COMPLETE


def test_min_filled_but_max_not_keeps_going():
    """When max_allowed is set above min, campaign stays active past min."""
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc),
                "min_required": 3,
                "max_allowed": 8,
            }
        ]
    )
    fill = se.FillSnapshot({str(svc): 3})  # at min, below max
    # No due waves and not complete -> NOOP (waiting for next wave)
    action = se.next_action(c, [], fill, _future_event())
    assert action.kind == se.ActionKind.NOOP


def test_max_filled_completes():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc),
                "min_required": 3,
                "max_allowed": 8,
            }
        ]
    )
    fill = se.FillSnapshot({str(svc): 8})
    action = se.next_action(c, [], fill, _future_event())
    assert action.kind == se.ActionKind.COMPLETE


# ── due wave logic ──


def test_no_due_waves_noop():
    svc = uuid.uuid4()
    c = _campaign(goals=[{"appointment_type_id": str(svc), "min_required": 3}])
    future_wave = _wave(svc, scheduled_at=_now() + timedelta(hours=1))
    action = se.next_action(
        c, [future_wave], se.FillSnapshot({str(svc): 0}), _future_event(),
        min_phase_service_ids={str(svc)},
    )
    assert action.kind == se.ActionKind.NOOP


def test_due_wave_triggers_send():
    svc = uuid.uuid4()
    c = _campaign(goals=[{"appointment_type_id": str(svc), "min_required": 3}])
    wave = _wave(svc, scheduled_at=_now() - timedelta(minutes=5))
    action = se.next_action(
        c, [wave], se.FillSnapshot({str(svc): 0}), _future_event(),
        min_phase_service_ids={str(svc)},
    )
    assert action.kind == se.ActionKind.SEND_WAVE
    assert action.wave_id == wave.id
    assert action.service_id == svc
    assert action.phase == "min"


def test_two_due_waves_picks_largest_shortfall_ratio():
    """Two services both have due waves AND both are min-phase; pick the
    one whose min shortfall is bigger."""
    svc_low = uuid.uuid4()   # 1/5 = 0.2 gap ratio
    svc_high = uuid.uuid4()  # 1/2 = 0.5 gap ratio
    c = _campaign(
        goals=[
            {"appointment_type_id": str(svc_low), "min_required": 5},
            {"appointment_type_id": str(svc_high), "min_required": 2},
        ]
    )
    waves = [
        _wave(svc_low, scheduled_at=_now() - timedelta(hours=1)),
        _wave(svc_high, scheduled_at=_now() - timedelta(hours=1)),
    ]
    fill = se.FillSnapshot({str(svc_low): 4, str(svc_high): 1})
    action = se.next_action(
        c, waves, fill, _future_event(),
        min_phase_service_ids={str(svc_low), str(svc_high)},
    )
    assert action.kind == se.ActionKind.SEND_WAVE
    assert action.service_id == svc_high


def test_min_phase_beats_max_phase_when_both_due():
    """Service A is in max-phase (cross-tenant min already met), service B
    is still in min-phase. Even with a smaller absolute gap, min wins."""
    svc_max = uuid.uuid4()  # max phase: gap to max
    svc_min = uuid.uuid4()  # min phase
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc_max),
                "min_required": 3,
                "max_allowed": 10,
            },
            {"appointment_type_id": str(svc_min), "min_required": 4},
        ]
    )
    waves = [
        _wave(svc_max, scheduled_at=_now() - timedelta(hours=1)),
        _wave(svc_min, scheduled_at=_now() - timedelta(hours=1)),
    ]
    # svc_max at 3 (= min, headed to max=10): max-phase target gap=7
    # svc_min at 0 (min=4): min-phase gap=4
    # Absolute gap favors max, but min-phase priority should win.
    fill = se.FillSnapshot({str(svc_max): 3, str(svc_min): 0})
    action = se.next_action(
        c, waves, fill, _future_event(),
        # Only svc_min is in min-phase across the tenant
        min_phase_service_ids={str(svc_min)},
    )
    assert action.kind == se.ActionKind.SEND_WAVE
    assert action.service_id == svc_min
    assert action.phase == "min"


def test_max_phase_when_all_min_globally_met():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc),
                "min_required": 3,
                "max_allowed": 8,
            }
        ]
    )
    wave = _wave(svc, scheduled_at=_now() - timedelta(minutes=5))
    fill = se.FillSnapshot({str(svc): 3})  # exactly at min
    # Empty min_phase set ⇒ everything's in max phase
    action = se.next_action(
        c, [wave], fill, _future_event(),
        min_phase_service_ids=set(),
    )
    assert action.kind == se.ActionKind.SEND_WAVE
    assert action.phase == "max"


def test_planned_only_waves_considered():
    svc = uuid.uuid4()
    c = _campaign(goals=[{"appointment_type_id": str(svc), "min_required": 3}])
    sent_wave = _wave(svc, scheduled_at=_now() - timedelta(days=1), status=WaveStatus.SENT)
    planned_wave = _wave(svc, scheduled_at=_now() - timedelta(minutes=5))
    action = se.next_action(
        c, [sent_wave, planned_wave], se.FillSnapshot({str(svc): 0}),
        _future_event(),
        min_phase_service_ids={str(svc)},
    )
    assert action.kind == se.ActionKind.SEND_WAVE
    assert action.wave_id == planned_wave.id


# ── closest-event sorting helper ──


def test_sort_campaigns_closest_first():
    c_far = _campaign()
    c_soon = _campaign()
    c_mid = _campaign()
    pairs = [
        (c_far, _now() + timedelta(days=30)),
        (c_soon, _now() + timedelta(days=2)),
        (c_mid, _now() + timedelta(days=10)),
    ]
    sorted_c = se.sort_campaigns_closest_event_first(pairs)
    assert sorted_c == [c_soon, c_mid, c_far]
