"""Tests for the pending-solicitation recall helper used by the
customer-side LLM preamble (Fix 2 — wave-to-reply context linking).
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.recruiter import chat_tools as ct


def _wave(
    *,
    minutes_ago: int,
    contact_ids: list[uuid.UUID],
    status: str = "sent",
    campaign_id: uuid.UUID | None = None,
    appt_type_id: uuid.UUID | None = None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        campaign_id=campaign_id or uuid.uuid4(),
        appointment_type_id=appt_type_id or uuid.uuid4(),
        status=SimpleNamespace(value=status),
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        targeted_contact_ids=[str(c) for c in contact_ids],
    )


def _scalars_returning(rows):
    """Build a mock result with .scalars().all() == rows."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result.scalars = MagicMock(return_value=scalars)
    return result


@pytest.mark.asyncio
async def test_get_pending_solicitation_none_when_contact_id_none():
    db = MagicMock()
    assert await ct.get_pending_solicitation(db, uuid.uuid4(), None) is None


@pytest.mark.asyncio
async def test_get_pending_solicitation_none_when_no_matching_waves():
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalars_returning([]))
    db.get = AsyncMock(return_value=None)
    cid = uuid.uuid4()
    assert await ct.get_pending_solicitation(db, uuid.uuid4(), cid) is None


@pytest.mark.asyncio
async def test_get_pending_solicitation_returns_most_recent_matching_wave():
    cid = uuid.uuid4()
    other = uuid.uuid4()
    older_wave = _wave(minutes_ago=600, contact_ids=[cid])
    newer_wave = _wave(minutes_ago=30, contact_ids=[cid])
    unrelated_wave = _wave(minutes_ago=10, contact_ids=[other])

    # ORDER BY scheduled_at DESC — give the mock pre-sorted rows
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=_scalars_returning([unrelated_wave, newer_wave, older_wave])
    )

    campaign = SimpleNamespace(
        id=newer_wave.campaign_id,
        event_slot_id=uuid.uuid4(),
    )
    slot = SimpleNamespace(
        id=campaign.event_slot_id,
        label="Food Drive",
        date=SimpleNamespace(isoformat=lambda: "2026-06-01"),
        start_time=SimpleNamespace(strftime=lambda fmt: "09:00"),
        end_time=SimpleNamespace(strftime=lambda fmt: "11:00"),
        location="YMCA",
    )
    appt_type = SimpleNamespace(
        id=newer_wave.appointment_type_id,
        name="Parking lot supervision",
    )

    async def fake_get(model, _id):
        # Return whichever sibling row matches the requested PK
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if "Campaign" in name:
            return campaign
        if "Slot" in name:
            return slot
        if "AppointmentType" in name:
            return appt_type
        return None

    db.get = AsyncMock(side_effect=fake_get)

    result = await ct.get_pending_solicitation(db, uuid.uuid4(), cid)

    assert result is not None
    assert result["wave_id"] == str(newer_wave.id)
    assert result["service_name"] == "Parking lot supervision"
    assert result["event_label"] == "Food Drive"
    assert result["event_date"] == "2026-06-01"
    assert result["event_start_time"] == "09:00"


def test_humanize_hours_ago_minutes():
    sent = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    assert "12 minute" in ct._humanize_hours_ago(sent)


def test_humanize_hours_ago_hours():
    sent = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=5)).isoformat()
    assert "3 hour" in ct._humanize_hours_ago(sent)


def test_humanize_hours_ago_days():
    sent = (datetime.now(timezone.utc) - timedelta(days=2, hours=1)).isoformat()
    assert "2 day" in ct._humanize_hours_ago(sent)


def test_humanize_hours_ago_recently_for_empty():
    assert ct._humanize_hours_ago("") == "recently"
