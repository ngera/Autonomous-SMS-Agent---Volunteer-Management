"""Tests for appointment type endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import make_list_result, make_scalar_result


def _make_appt_type(**overrides):
    t = MagicMock()
    t.id = overrides.get("id", uuid.uuid4())
    t.name = overrides.get("name", "Haircut")
    t.category = overrides.get("category", "Grooming")
    t.duration_minutes = 60
    t.price = 45.00
    t.description = "Standard haircut"
    t.is_active = True
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


def _populate_appt_type(obj):
    """Side effect for db.refresh to populate fields on new AppointmentType."""
    async def _refresh(instance):
        instance.id = uuid.uuid4()
        instance.is_active = True
        instance.created_at = datetime.now(timezone.utc)
        instance.updated_at = datetime.now(timezone.utc)
        instance.description = None
    return _refresh


@pytest.mark.asyncio
async def test_list_appointment_types(client, mock_db):
    mock_db.execute.return_value = make_list_result([_make_appt_type()])
    resp = await client.get("/api/v1/appointment-types")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_appointment_type(client, mock_db):
    mock_db.refresh = AsyncMock(side_effect=_populate_appt_type(None))
    resp = await client.post("/api/v1/appointment-types", json={
        "name": "New Type",
        "category": "Grooming",
        "duration_minutes": 30,
        "price": 25.00,
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_appointment_type(client, mock_db):
    appt = _make_appt_type()
    mock_db.execute.return_value = make_scalar_result(appt)
    mock_db.refresh = AsyncMock()

    resp = await client.put(f"/api/v1/appointment-types/{appt.id}", json={
        "name": "Updated Name",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_appointment_type_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.put(f"/api/v1/appointment-types/{uuid.uuid4()}", json={
        "name": "X",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_related_services(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get(f"/api/v1/appointment-types/{uuid.uuid4()}/related")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_requires_manager(client, mock_db, staff_user, auth_as):
    auth_as(staff_user)
    resp = await client.post("/api/v1/appointment-types", json={
        "name": "New",
        "category": "Grooming",
        "duration_minutes": 30,
        "price": 25.00,
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_appointment_types_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/appointment-types")
    assert resp.status_code in (401, 403)
