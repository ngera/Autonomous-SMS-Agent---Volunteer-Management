"""Unit tests for the recruiter targeting layer.

Most tests exercise pure helpers (no DB). One end-to-end test mocks the
entire query sequence in ``select_recipients`` to verify the filter order
and ranking under realistic conditions.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.recruiter import targeting as t
from app.models.recruitment_campaign import RecruitmentCampaign


def _campaign(policy: dict | None = None, goals: list | None = None):
    c = MagicMock(spec=RecruitmentCampaign)
    c.id = uuid.uuid4()
    c.tenant_id = uuid.uuid4()
    c.policy = policy or {}
    c.goals = goals or []
    return c


def _scored(
    score: float,
    ts: datetime | None = None,
    name: str = "x",
) -> t.ScoredContact:
    return t.ScoredContact(
        contact_id=uuid.uuid4(),
        name=name,
        phone="+15550000000",
        score=score,
        this_service_count=0,
        same_category_count=0,
        no_show_count=0,
        most_recent_qualifying_at=ts,
    )


# ── _wave_size ──

def test_wave_size_zero_when_already_filled():
    svc = uuid.uuid4()
    c = _campaign(goals=[{"appointment_type_id": str(svc), "target": 5}])
    assert t._wave_size(c, svc, current_signups=5) == 0
    assert t._wave_size(c, svc, current_signups=6) == 0


def test_wave_size_applies_overshoot():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 8}],
        policy={"overshoot_factor": 1.5},
    )
    # gap=8, 8*1.5 = 12
    assert t._wave_size(c, svc, current_signups=0) == 12
    # gap=3, 3*1.5 = 4.5 → ceil 5
    assert t._wave_size(c, svc, current_signups=5) == 5


def test_wave_size_respects_absolute_cap():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 50}],
        policy={"overshoot_factor": 2.0, "per_wave_absolute_cap": 20},
    )
    # gap=50, 50*2=100 → capped at 20
    assert t._wave_size(c, svc, current_signups=0) == 20


def test_wave_size_floor_of_one_when_gap_exists():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 1}],
        policy={"overshoot_factor": 0.1},
    )
    # 1*0.1 = 0.1 → ceil 1, but max(1, 1) = 1
    assert t._wave_size(c, svc, current_signups=0) == 1


def test_wave_size_unknown_service_returns_zero():
    c = _campaign(goals=[])
    assert t._wave_size(c, uuid.uuid4(), current_signups=0) == 0


# ── _rank ──

def test_rank_orders_by_score_descending():
    a = _scored(score=10.0, name="alice")
    b = _scored(score=20.0, name="bob")
    c = _scored(score=5.0, name="carol")
    result = t._rank([a, b, c])
    assert [r.score for r in result] == [20.0, 10.0, 5.0]


def test_rank_breaks_score_tie_by_recency():
    old = _scored(
        score=10.0,
        ts=datetime(2025, 1, 1, tzinfo=timezone.utc),
        name="alice",
    )
    new = _scored(
        score=10.0,
        ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        name="bob",
    )
    result = t._rank([old, new])
    assert result[0] is new
    assert result[1] is old


def test_rank_breaks_remaining_tie_alphabetically():
    a = _scored(score=10.0, name="bob")
    b = _scored(score=10.0, name="alice")
    result = t._rank([a, b])
    assert [r.name for r in result] == ["alice", "bob"]


def test_rank_handles_none_timestamps_and_names():
    a = _scored(score=10.0, name=None)
    b = _scored(score=10.0, name="alice")
    result = t._rank([a, b])
    # Empty name sorts before "alice" since "" < "alice"
    assert result[0].name is None


# ── _service_target ──

def test_service_target_found_legacy_target_key():
    """Legacy goal shape with 'target' still resolves as min_required."""
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {"appointment_type_id": str(uuid.uuid4()), "target": 3},
            {"appointment_type_id": str(svc), "target": 7},
        ]
    )
    assert t._service_target(c, svc) == 7
    assert t._service_target(c, svc, phase="min") == 7


def test_service_target_min_required_key():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "min_required": 4}]
    )
    assert t._service_target(c, svc, phase="min") == 4


def test_service_target_max_phase_uses_max_allowed():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc),
                "min_required": 3,
                "max_allowed": 7,
            }
        ]
    )
    assert t._service_target(c, svc, phase="min") == 3
    assert t._service_target(c, svc, phase="max") == 7


def test_service_target_max_phase_falls_back_to_min_when_no_max():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[{"appointment_type_id": str(svc), "min_required": 3}]
    )
    # No max_allowed → max phase target == min target
    assert t._service_target(c, svc, phase="max") == 3


def test_service_target_missing_returns_zero():
    c = _campaign(goals=[])
    assert t._service_target(c, uuid.uuid4()) == 0


# ── _wave_size by phase ──

def test_wave_size_min_vs_max_phase():
    svc = uuid.uuid4()
    c = _campaign(
        goals=[
            {
                "appointment_type_id": str(svc),
                "min_required": 4,
                "max_allowed": 10,
            }
        ],
        policy={"overshoot_factor": 1.0},
    )
    # In min phase: gap = 4 - 0 = 4
    assert t._wave_size(c, svc, current_signups=0, phase="min") == 4
    # In max phase: gap = 10 - 0 = 10
    assert t._wave_size(c, svc, current_signups=0, phase="max") == 10
    # In min phase with min already met: 0 (recruitment for this service
    # paused until max-phase kicks in)
    assert t._wave_size(c, svc, current_signups=4, phase="min") == 0
    # In max phase with min met but max not: still has gap
    assert t._wave_size(c, svc, current_signups=4, phase="max") == 6


# ── policy getters with defaults ──

def test_policy_defaults():
    c = _campaign(policy={})
    assert t._cooldown_hours(c) == t.DEFAULT_COOLDOWN_HOURS_WITHIN_CAMPAIGN
    assert t._global_cooldown_hours(c) == t.DEFAULT_GLOBAL_PER_CONTACT_HOURS
    assert t._lookback_days(c) == t.DEFAULT_EXPERIENCE_LOOKBACK_DAYS
    assert t._overshoot_factor(c) == t.DEFAULT_OVERSHOOT_FACTOR
    assert t._absolute_cap(c) is None


def test_policy_overrides_applied():
    c = _campaign(
        policy={
            "cooldown_hours_within_campaign": 12,
            "global_per_contact_hours": 6,
            "experience_lookback_days": 90,
            "overshoot_factor": 2.0,
            "per_wave_absolute_cap": 15,
        }
    )
    assert t._cooldown_hours(c) == 12
    assert t._global_cooldown_hours(c) == 6
    assert t._lookback_days(c) == 90
    assert t._overshoot_factor(c) == 2.0
    assert t._absolute_cap(c) == 15


# ── select_recipients (high-level integration with mocked DB) ──

@pytest.mark.asyncio
async def test_select_recipients_returns_empty_when_no_service_eligible():
    """When nobody is configured for the service, return empty with a clear reason."""
    svc = uuid.uuid4()
    campaign = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 5}],
    )
    event = MagicMock()
    event.tenant_id = campaign.tenant_id
    event.date = datetime(2026, 6, 1).date()

    db = AsyncMock()

    # _eligible_for_service: both subqueries return empty
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute.return_value = empty

    result = await t.select_recipients(db, campaign, event, svc, wave_number=1)

    assert result.contacts == []
    assert result.eligible_pool_size == 0
    assert "configured" in result.selection_reason.lower()


@pytest.mark.asyncio
async def test_select_recipients_skips_when_service_already_filled():
    """If current signups already meet the target, mark wave as filled."""
    from app.models.contact import Contact, ContactStatus

    svc = uuid.uuid4()
    eligible_id = uuid.uuid4()
    campaign = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 3}],
        policy={"overshoot_factor": 1.5},
    )
    event = MagicMock()
    event.tenant_id = campaign.tenant_id
    event.date = datetime(2026, 6, 1).date()

    contact = MagicMock(spec=Contact)
    contact.id = eligible_id
    contact.tenant_id = campaign.tenant_id
    contact.name = "alice"
    contact.phone = "+15551112222"
    contact.status = ContactStatus.ACTIVE
    contact.is_archived = False
    contact.all_services_enabled = True

    # Sequence of db.execute results matching the order of queries inside
    # select_recipients:
    # 1. _eligible_for_service: all_services_enabled query → [eligible_id]
    # 2. _eligible_for_service: preferred query → []
    # 3. _opted_in_active_contacts → [contact]
    # 4. _active_suspensions → []
    # 5. _already_booked_in_event → []
    # 6. _within_campaign_cooldown: waves query → []
    # 7. _within_global_cooldown: waves query → []
    # 8. _score_candidates: this-service → []
    # 9. _category_for_service → "general"
    # 10. _score_candidates: same-category → []
    # 11. _score_candidates: no-show → []
    # 12. _current_signups_for_service → 3 (already filled)
    def _r(items=None, scalar=None, all_rows=None):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items or []
        r.scalar.return_value = scalar
        r.scalar_one_or_none.return_value = scalar
        r.all.return_value = all_rows or []
        return r

    db = AsyncMock()
    db.execute.side_effect = [
        _r(items=[eligible_id]),       # all_services_enabled
        _r(items=[]),                  # preferred
        _r(items=[contact]),           # opted-in active
        _r(items=[]),                  # suspensions
        _r(items=[]),                  # already booked
        _r(items=[]),                  # campaign cooldown waves
        _r(items=[]),                  # global cooldown waves
        _r(scalar="general"),          # category for service
        _r(all_rows=[]),               # this-service score query
        _r(all_rows=[]),               # same-category score query
        _r(all_rows=[]),               # no-show score query
        _r(scalar=3),                  # current signups = target
    ]

    result = await t.select_recipients(db, campaign, event, svc, wave_number=2)

    assert result.contacts == []
    assert "already at" in result.selection_reason.lower()
    assert result.eligible_pool_size == 1


@pytest.mark.asyncio
async def test_select_recipients_filters_then_ranks_and_caps():
    """Happy path: eligible pool > wave size; top scorers selected."""
    from app.models.contact import Contact, ContactStatus

    svc = uuid.uuid4()
    campaign = _campaign(
        goals=[{"appointment_type_id": str(svc), "target": 2}],
        policy={"overshoot_factor": 1.5},
    )
    event = MagicMock()
    event.tenant_id = campaign.tenant_id
    event.date = datetime(2026, 6, 1).date()

    # Three eligible contacts; wave size = ceil(2 * 1.5) = 3 so all selected,
    # but ranking should put the highest scorer first.
    ids = [uuid.uuid4() for _ in range(3)]

    def _mk_contact(cid, name):
        c = MagicMock(spec=Contact)
        c.id = cid
        c.tenant_id = campaign.tenant_id
        c.name = name
        c.phone = f"+155500000{name[-1]}"
        c.status = ContactStatus.ACTIVE
        c.is_archived = False
        c.all_services_enabled = True
        return c

    contacts = [_mk_contact(ids[i], f"v{i}") for i in range(3)]
    now = datetime.now(timezone.utc)

    def _r(items=None, scalar=None, all_rows=None):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items or []
        r.scalar.return_value = scalar
        r.scalar_one_or_none.return_value = scalar
        r.all.return_value = all_rows or []
        return r

    db = AsyncMock()
    db.execute.side_effect = [
        _r(items=ids),                          # all_services_enabled
        _r(items=[]),                           # preferred
        _r(items=contacts),                     # opted-in active
        _r(items=[]),                           # suspensions
        _r(items=[]),                           # already booked
        _r(items=[]),                           # campaign cooldown waves
        _r(items=[]),                           # global cooldown waves
        _r(scalar="general"),                   # category
        _r(all_rows=[                           # this-service counts
            (ids[0], 1, now),
            (ids[1], 3, now),
            (ids[2], 2, now),
        ]),
        _r(all_rows=[]),                        # same-category
        _r(all_rows=[]),                        # no-show
        _r(scalar=0),                           # current signups
    ]

    result = await t.select_recipients(db, campaign, event, svc, wave_number=1)

    assert len(result.contacts) == 3
    # ids[1] had 3 this-service bookings → score 30, ranked first
    assert result.contacts[0].contact_id == ids[1]
    assert result.contacts[0].score == 30.0
    assert result.eligible_pool_size == 3
    assert "Wave 1" in result.selection_reason
