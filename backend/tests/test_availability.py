"""Tests for availability endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import make_list_result, make_scalar_result


def _populate_rule(instance):
    """Side effect for db.refresh to populate AvailabilityRule fields."""
    instance.id = uuid.uuid4()


def _populate_blocked_date(instance):
    """Side effect for db.refresh to populate BlockedDate fields."""
    instance.id = uuid.uuid4()
    instance.created_at = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_rules(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/availability/rules")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_rules(client, mock_db):
    mock_db.refresh = AsyncMock(side_effect=_populate_rule)
    resp = await client.put("/api/v1/availability/rules", json={
        "rules": [
            {
                "day_of_week": 1,
                "start_time": "09:00",
                "end_time": "17:00",
                "slot_duration_minutes": 60,
                "buffer_minutes": 0,
                "is_active": True,
            }
        ]
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_blocked_dates(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/availability/blocked-dates")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_blocked_date(client, mock_db):
    mock_db.refresh = AsyncMock(side_effect=_populate_blocked_date)
    resp = await client.post("/api/v1/availability/blocked-dates", json={
        "date_from": "2025-12-25",
        "date_to": "2025-12-26",
        "reason": "Christmas",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_blocked_date(client, mock_db):
    blocked = MagicMock()
    blocked.id = uuid.uuid4()
    mock_db.execute.return_value = make_scalar_result(blocked)
    mock_db.delete = AsyncMock()
    resp = await client.delete(f"/api/v1/availability/blocked-dates/{blocked.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_availability_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/availability/rules")
    assert resp.status_code in (401, 403)
