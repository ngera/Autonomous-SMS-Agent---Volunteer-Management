"""Tests for analytics endpoints."""

import pytest

from tests.conftest import make_list_result, make_scalar_result


@pytest.mark.asyncio
async def test_booking_analytics(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/analytics/bookings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_revenue_analytics(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/analytics/revenue")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_retention_analytics(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(0)
    resp = await client.get("/api/v1/analytics/retention")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reminder_analytics(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(0)
    resp = await client.get("/api/v1/analytics/reminders")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_consent_analytics(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(0)
    resp = await client.get("/api/v1/analytics/consent")
    assert resp.status_code == 200
