"""Tests for customer endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.contact import ContactStatus
from tests.conftest import make_list_result, make_scalar_result


def _make_contact(**overrides):
    c = MagicMock()
    c.phone = overrides.get("phone", "+447700900000")
    c.name = overrides.get("name", "Test Customer")
    c.email = overrides.get("email", "customer@test.com")
    c.status = ContactStatus.ACTIVE
    c.reminder_preference_days = 7
    c.created_at = datetime.now(timezone.utc)
    c.updated_at = datetime.now(timezone.utc)
    c.consent = None  # No consent record
    return c


@pytest.mark.asyncio
async def test_list_customers(client, mock_db):
    mock_db.execute.side_effect = [
        make_scalar_result(0),
        make_list_result([]),
    ]
    resp = await client.get("/api/v1/customers")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_customer(client, mock_db):
    contact = _make_contact()
    mock_db.execute.return_value = make_scalar_result(contact)
    resp = await client.get("/api/v1/customers/%2B447700900000")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_customer_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.get("/api/v1/customers/%2B447700999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_customer(client, mock_db):
    contact = _make_contact()
    mock_db.execute.return_value = make_scalar_result(contact)
    mock_db.refresh = AsyncMock()

    resp = await client.put("/api/v1/customers/%2B447700900000", json={
        "name": "Updated Name",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_customer_bookings(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/customers/%2B447700900000/bookings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_customer_conversations(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/customers/%2B447700900000/conversations")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_customer_pattern(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/customers/%2B447700900000/pattern")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_customers_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/customers")
    assert resp.status_code in (401, 403)
