"""Tests for booking endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.booking import BookingStatus
from tests.conftest import make_list_result, make_scalar_result


def _make_booking(**overrides):
    b = MagicMock()
    b.id = overrides.get("id", uuid.uuid4())
    b.contact_phone = overrides.get("contact_phone", "+447700900000")
    b.appointment_type_id = overrides.get("appointment_type_id", uuid.uuid4())
    b.scheduled_at = overrides.get("scheduled_at", datetime.now(timezone.utc))
    b.confirmed_at = None
    b.completed_at = None
    b.status = overrides.get("status", BookingStatus.SCHEDULED)
    b.price_at_booking = overrides.get("price_at_booking", 50.00)
    b.calendar_event_id = None
    b.ics_sequence = 0
    b.ics_new_url = None
    b.ics_update_url = None
    b.conversation_id = None
    b.created_at = datetime.now(timezone.utc)
    return b


@pytest.mark.asyncio
async def test_list_bookings(client, mock_db):
    booking = _make_booking()
    mock_db.execute.side_effect = [
        make_scalar_result(1),
        make_list_result([booking]),
    ]
    resp = await client.get("/api/v1/bookings")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_booking(client, mock_db):
    booking = _make_booking()
    mock_db.execute.return_value = make_scalar_result(booking)
    resp = await client.get(f"/api/v1/bookings/{uuid.uuid4()}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_booking_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.get(f"/api/v1/bookings/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_booking(client, mock_db):
    appt_type = MagicMock()
    appt_type.id = uuid.uuid4()

    mock_db.execute.return_value = make_scalar_result(appt_type)

    def _populate_booking(instance):
        instance.id = uuid.uuid4()
        instance.ics_sequence = 0
        instance.ics_new_url = None
        instance.ics_update_url = None
        instance.calendar_event_id = None
        instance.conversation_id = None
        instance.completed_at = None
        instance.created_at = datetime.now(timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=_populate_booking)

    with patch("app.services.booking.process_booking_creation", new_callable=AsyncMock):
        resp = await client.post("/api/v1/bookings", json={
            "contact_phone": "+447700900000",
            "appointment_type_id": str(appt_type.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "price_at_booking": 50.00,
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_booking_staff_forbidden(client, mock_db, staff_user, auth_as):
    auth_as(staff_user)
    resp = await client.post("/api/v1/bookings", json={
        "contact_phone": "+447700900000",
        "appointment_type_id": str(uuid.uuid4()),
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "price_at_booking": 50.00,
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_booking_history(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get(f"/api/v1/bookings/{uuid.uuid4()}/history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cancel_booking(client, mock_db):
    booking = _make_booking(status=BookingStatus.SCHEDULED)

    mock_db.execute.return_value = make_scalar_result(booking)

    with patch("app.services.booking.process_booking_cancellation", new_callable=AsyncMock):
        resp = await client.delete(f"/api/v1/bookings/{booking.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_bookings_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/bookings")
    assert resp.status_code in (401, 403)
