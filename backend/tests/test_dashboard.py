"""Tests for dashboard endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_scalar_result, make_list_result


@pytest.mark.asyncio
async def test_get_summary(client, mock_db):
    # Dashboard makes many count queries — all return 0
    mock_db.execute.return_value = make_scalar_result(0)
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "todays_bookings_count" in data
    assert "monthly_revenue" in data


@pytest.mark.asyncio
async def test_get_todays_bookings(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/dashboard/todays-bookings")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_notifications(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/dashboard/notifications")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mark_notification_read(client, mock_db):
    notif = MagicMock()
    notif.id = uuid.uuid4()
    notif.read_at = None
    mock_db.execute.return_value = make_scalar_result(notif)

    resp = await client.put(f"/api/v1/dashboard/notifications/{notif.id}/read")
    assert resp.status_code == 200
