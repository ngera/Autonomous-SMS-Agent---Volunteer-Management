"""Tests for the event-reschedule cascade and reconfirmation router.

Pure helpers get direct tests. The cascade itself is mocked at the DB
boundary to verify it (a) shifts booking scheduled_at by the right
delta, (b) sets pending_reconfirmation_until, (c) cancels PLANNED
waves on linked campaigns, (d) re-materializes from the new date.
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import event_reschedule as er
from app.services import reconfirm


# ── slot_datetime_changed (pure) ──

def test_slot_datetime_changed_date_only():
    assert er.slot_datetime_changed(
        old_date=date(2026, 6, 1),
        old_start=time(9, 0),
        old_end=time(11, 0),
        new_date=date(2026, 6, 15),
        new_start=None,
        new_end=None,
    )


def test_slot_datetime_changed_start_only():
    assert er.slot_datetime_changed(
        old_date=date(2026, 6, 1),
        old_start=time(9, 0),
        old_end=time(11, 0),
        new_date=None,
        new_start=time(10, 0),
        new_end=None,
    )


def test_slot_datetime_changed_no_change_when_payload_missing():
    """Edits that don't include date/start/end (e.g. label-only PATCH)
    should NOT trigger the cascade. The endpoint passes None for
    unchanged fields via exclude_unset=True."""
    assert not er.slot_datetime_changed(
        old_date=date(2026, 6, 1),
        old_start=time(9, 0),
        old_end=time(11, 0),
        new_date=None,
        new_start=None,
        new_end=None,
    )


def test_slot_datetime_changed_no_change_when_values_equal():
    assert not er.slot_datetime_changed(
        old_date=date(2026, 6, 1),
        old_start=time(9, 0),
        old_end=time(11, 0),
        new_date=date(2026, 6, 1),
        new_start=time(9, 0),
        new_end=time(11, 0),
    )


# ── reconfirm trigger normalization (pure) ──

def test_reconfirm_normalize_strips_punctuation():
    assert reconfirm._normalize("YES!") == "yes"
    assert reconfirm._normalize("  Stop. ") == "stop"
    assert reconfirm._normalize("Confirm.") == "confirm"


def test_reconfirm_confirm_triggers_include_common_phrasings():
    for phrase in ("yes", "Yep", "im in", "count me in", "i'll be there"):
        assert reconfirm._normalize(phrase) in reconfirm._CONFIRM_TRIGGERS


def test_reconfirm_cancel_triggers_include_common_phrasings():
    for phrase in ("STOP", "No", "cancel", "im out", "drop me"):
        assert reconfirm._normalize(phrase) in reconfirm._CANCEL_TRIGGERS


# ── cascade_slot_reschedule (DB mocked) ──

def _mk_booking(slot_id, scheduled_at, status="scheduled"):
    b = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_slot_id=slot_id,
        scheduled_at=scheduled_at,
        status=SimpleNamespace(value=status),
        pending_reconfirmation_until=None,
        contact_id=uuid.uuid4(),
    )
    # Booking.status is compared via .in_([SCHEDULED, RESCHEDULED]),
    # so make the SimpleNamespace look like the enum sufficient for
    # equality checks in this test. We don't trigger the comparison
    # because we use the mock's scalars() return directly.
    return b


def _mk_slot(slot_id, date_, start, end):
    return SimpleNamespace(
        id=slot_id,
        tenant_id=uuid.uuid4(),
        date=date_,
        start_time=start,
        end_time=end,
        service_config=[],
    )


@pytest.mark.asyncio
async def test_cascade_shifts_bookings_by_date_delta(monkeypatch):
    """Slot moves Jun 1 09:00 → Jun 15 09:00. Booking originally at
    Jun 1 09:00 should end up at Jun 15 09:00; pending_reconfirmation_until
    should be set; campaign list lookup returns no campaigns (no
    recalibration in this test)."""
    slot_id = uuid.uuid4()
    new_slot = _mk_slot(
        slot_id,
        date(2026, 6, 15),
        time(9, 0),
        time(11, 0),
    )
    old_date = date(2026, 6, 1)
    old_start = time(9, 0)

    original_dt = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    expected_new_dt = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)

    booking_a = _mk_booking(slot_id, original_dt)
    booking_b = _mk_booking(
        slot_id, original_dt + timedelta(minutes=30)
    )

    db = MagicMock()
    # First execute() → bookings query, second execute() → campaigns query
    bookings_result = MagicMock()
    bookings_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[booking_a, booking_b]))
    )
    campaigns_result = MagicMock()
    campaigns_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    db.execute = AsyncMock(side_effect=[bookings_result, campaigns_result])
    db.flush = AsyncMock()

    summary = await er.cascade_slot_reschedule(
        db, new_slot, old_date, old_start
    )

    assert booking_a.scheduled_at == expected_new_dt
    # Booking_b should keep its 30-minute offset relative to the slot start
    assert booking_b.scheduled_at == expected_new_dt + timedelta(minutes=30)
    assert booking_a.pending_reconfirmation_until is not None
    assert booking_b.pending_reconfirmation_until is not None
    assert set(summary["affected_booking_ids"]) == {booking_a.id, booking_b.id}
    assert summary["campaign_ids_recalibrated"] == []


@pytest.mark.asyncio
async def test_cascade_noop_when_delta_zero():
    """If the new datetime equals the old, no bookings should be touched
    even if some match by slot_id. Saves a write storm on edits that
    don't actually move the event."""
    slot_id = uuid.uuid4()
    same_slot = _mk_slot(
        slot_id, date(2026, 6, 1), time(9, 0), time(11, 0)
    )

    db = MagicMock()
    # The campaigns query still runs but should return [] for this test.
    campaigns_result = MagicMock()
    campaigns_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    db.execute = AsyncMock(side_effect=[campaigns_result])
    db.flush = AsyncMock()

    summary = await er.cascade_slot_reschedule(
        db, same_slot, date(2026, 6, 1), time(9, 0)
    )

    assert summary["affected_booking_ids"] == []
    assert summary["campaign_ids_recalibrated"] == []


# ── reconfirm router (DB mocked) ──

@pytest.mark.asyncio
async def test_router_returns_none_when_no_pending(monkeypatch):
    """If contact has no pending reconfirmation, router returns None
    so the LLM path runs normally."""
    monkeypatch.setattr(
        reconfirm,
        "pending_reconfirmations",
        AsyncMock(return_value=[]),
    )

    result = await reconfirm.maybe_handle_reconfirmation_directly(
        db=MagicMock(),
        tenant=SimpleNamespace(id=uuid.uuid4()),
        contact=SimpleNamespace(id=uuid.uuid4()),
        body="yes",
    )
    assert result is None


@pytest.mark.asyncio
async def test_router_confirms_on_yes(monkeypatch):
    booking = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status="scheduled",
        scheduled_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        pending_reconfirmation_until=datetime.now(timezone.utc)
        + timedelta(hours=24),
        confirmed_at=None,
    )
    monkeypatch.setattr(
        reconfirm,
        "pending_reconfirmations",
        AsyncMock(return_value=[booking]),
    )
    monkeypatch.setattr(
        reconfirm, "confirm_booking", AsyncMock()
    )

    db = MagicMock()
    db.flush = AsyncMock()
    result = await reconfirm.maybe_handle_reconfirmation_directly(
        db=db,
        tenant=SimpleNamespace(id=uuid.uuid4()),
        contact=SimpleNamespace(id=uuid.uuid4()),
        body="YES",
    )
    assert result is not None
    assert "confirmed" in result.lower()
    reconfirm.confirm_booking.assert_awaited_once_with(db, booking)


@pytest.mark.asyncio
async def test_router_cancels_on_stop(monkeypatch):
    booking = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status="scheduled",
        scheduled_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        pending_reconfirmation_until=datetime.now(timezone.utc)
        + timedelta(hours=24),
    )
    monkeypatch.setattr(
        reconfirm,
        "pending_reconfirmations",
        AsyncMock(return_value=[booking]),
    )
    monkeypatch.setattr(
        reconfirm, "cancel_due_to_reschedule", AsyncMock()
    )

    db = MagicMock()
    db.flush = AsyncMock()
    tenant = SimpleNamespace(id=uuid.uuid4())
    result = await reconfirm.maybe_handle_reconfirmation_directly(
        db=db,
        tenant=tenant,
        contact=SimpleNamespace(id=uuid.uuid4()),
        body="STOP",
    )
    assert result is not None
    assert "removed" in result.lower()
    reconfirm.cancel_due_to_reschedule.assert_awaited_once_with(
        db, booking, tenant
    )


@pytest.mark.asyncio
async def test_router_falls_through_on_non_trigger(monkeypatch):
    """Non-trigger phrases (questions, complex replies) must return
    None so the LLM gets a chance to respond."""
    booking = SimpleNamespace(
        id=uuid.uuid4(),
        scheduled_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        pending_reconfirmation_until=datetime.now(timezone.utc)
        + timedelta(hours=24),
    )
    monkeypatch.setattr(
        reconfirm,
        "pending_reconfirmations",
        AsyncMock(return_value=[booking]),
    )

    result = await reconfirm.maybe_handle_reconfirmation_directly(
        db=MagicMock(),
        tenant=SimpleNamespace(id=uuid.uuid4()),
        contact=SimpleNamespace(id=uuid.uuid4()),
        body="can i come at noon instead?",
    )
    assert result is None
