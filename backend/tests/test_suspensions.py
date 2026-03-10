"""Tests for suspension endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.contact_consent import ConsentStatus
from app.models.suspension import SuspensionType
from tests.conftest import make_list_result, make_scalar_result


def _make_suspension(**overrides):
    s = MagicMock()
    s.id = overrides.get("id", uuid.uuid4())
    s.contact_phone = "+447700900000"
    s.suspended_at = datetime.now(timezone.utc)
    s.suspension_type = SuspensionType.MANUAL
    s.reason = "Abusive language"
    s.strike_ids = None
    s.conversation_id = None
    s.notification_sent_at = None
    s.reviewed_by_admin_id = None
    s.reviewed_at = None
    s.review_decision = None
    s.review_notes = None
    s.lifted_at = None
    return s


@pytest.mark.asyncio
async def test_list_suspensions(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/suspensions")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_suspension(client, mock_db):
    susp = _make_suspension()
    mock_db.execute.return_value = make_scalar_result(susp)
    resp = await client.get(f"/api/v1/suspensions/{susp.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_suspension_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.get(f"/api/v1/suspensions/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lift_suspension(client, mock_db):
    susp = _make_suspension()
    contact = MagicMock()
    consent = MagicMock()
    consent.status = ConsentStatus.BLOCKED

    mock_db.execute.side_effect = [
        make_scalar_result(susp),
        make_scalar_result(contact),
        make_scalar_result(consent),
    ]
    mock_db.refresh = AsyncMock()

    resp = await client.post(f"/api/v1/suspensions/{susp.id}/lift", json={
        "notes": "Warning issued",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_suspension(client, mock_db):
    susp = _make_suspension()
    mock_db.execute.return_value = make_scalar_result(susp)
    mock_db.refresh = AsyncMock()

    resp = await client.post(f"/api/v1/suspensions/{susp.id}/confirm", json={
        "notes": "Confirmed abusive",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ban_user(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    susp = _make_suspension()
    contact = MagicMock()

    mock_db.execute.side_effect = [
        make_scalar_result(susp),
        make_scalar_result(contact),
    ]
    mock_db.refresh = AsyncMock()

    resp = await client.post(f"/api/v1/suspensions/{susp.id}/ban", json={
        "notes": "Permanent ban",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ban_user_staff_forbidden(client, mock_db, staff_user, auth_as):
    auth_as(staff_user)
    resp = await client.post(f"/api/v1/suspensions/{uuid.uuid4()}/ban", json={
        "notes": "test",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manual_suspend(client, mock_db):
    contact = MagicMock()
    consent = MagicMock()

    mock_db.execute.side_effect = [
        make_scalar_result(contact),
        make_scalar_result(consent),
    ]

    def _populate_suspension(instance):
        instance.id = uuid.uuid4()
        instance.suspended_at = datetime.now(timezone.utc)
        instance.strike_ids = None
        instance.conversation_id = None
        instance.reviewed_by_admin_id = None
        instance.reviewed_at = None
        instance.review_decision = None
        instance.review_notes = None
        instance.lifted_at = None

    mock_db.refresh = AsyncMock(side_effect=_populate_suspension)

    resp = await client.post("/api/v1/suspensions/customers/%2B447700900000/suspend", json={
        "reason": "Manual suspension reason",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_manual_suspend_customer_not_found(client, mock_db):
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.post("/api/v1/suspensions/customers/%2B447700999999/suspend", json={
        "reason": "test",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspensions_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/suspensions")
    assert resp.status_code in (401, 403)
