"""Tests for reminder endpoints."""

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.reminder import ReminderStatus
from tests.conftest import make_list_result, make_scalar_result


def _populate_reminder(instance):
    """Side effect for db.refresh to populate Reminder fields after creation."""
    instance.id = uuid.uuid4()
    instance.pattern_snapshot = None
    instance.follow_up_sent_at = None
    instance.converted_to_booking_id = None
    instance.skip_reason = None
    instance.created_at = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_upcoming_reminders(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/reminders/upcoming")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_reminder_history(client, mock_db):
    mock_db.execute.side_effect = [
        make_scalar_result(0),
        make_list_result([]),
    ]
    resp = await client.get("/api/v1/reminders/history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_trigger_reminder(client, mock_db):
    mock_db.refresh = AsyncMock(side_effect=_populate_reminder)
    resp = await client.post("/api/v1/reminders/trigger", json={
        "contact_phone": "+447700900000",
        "appointment_type_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_trigger_reminder_staff_forbidden(client, mock_db, staff_user, auth_as):
    auth_as(staff_user)
    resp = await client.post("/api/v1/reminders/trigger", json={
        "contact_phone": "+447700900000",
        "appointment_type_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_reminder(client, mock_db):
    reminder = MagicMock()
    reminder.id = uuid.uuid4()
    reminder.status = ReminderStatus.PENDING

    mock_db.execute.return_value = make_scalar_result(reminder)

    # httpx DELETE with body requires using request()
    resp = await client.request(
        "DELETE",
        f"/api/v1/reminders/{reminder.id}",
        content=json.dumps({"reason": "Customer requested"}),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cancel_reminder_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.request(
        "DELETE",
        f"/api/v1/reminders/{uuid.uuid4()}",
        content=json.dumps({"reason": "test"}),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reminder_analytics(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(0)
    resp = await client.get("/api/v1/reminders/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sent" in data
    assert "conversion_rate" in data


@pytest.mark.asyncio
async def test_reminders_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/reminders/upcoming")
    assert resp.status_code in (401, 403)
