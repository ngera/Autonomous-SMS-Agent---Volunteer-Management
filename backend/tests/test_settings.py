"""Tests for settings endpoints."""

import pytest

from tests.conftest import make_list_result, make_scalar_result


@pytest.mark.asyncio
async def test_get_settings(client, mock_db):
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_settings(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    mock_db.execute.return_value = make_scalar_result(None)  # no existing setting
    resp = await client.put("/api/v1/settings", json={
        "settings": {"business_name": "Test Salon"},
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_settings_staff_forbidden(client, mock_db, staff_user, auth_as):
    auth_as(staff_user)
    resp = await client.put("/api/v1/settings", json={
        "settings": {"key": "value"},
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_settings_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/settings")
    assert resp.status_code in (401, 403)
