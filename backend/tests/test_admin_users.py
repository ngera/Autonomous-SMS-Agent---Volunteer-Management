"""Tests for admin user endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.admin_user import AdminRole
from tests.conftest import make_list_result, make_scalar_result


def _make_admin_user(**overrides):
    u = MagicMock()
    u.id = overrides.get("id", uuid.uuid4())
    u.email = overrides.get("email", "staff@test.com")
    u.role = overrides.get("role", AdminRole.STAFF)
    u.is_active = True
    u.created_at = datetime.now(timezone.utc)
    u.last_login_at = None
    return u


def _populate_admin_user(instance):
    """Side effect for db.refresh to populate AdminUser fields."""
    instance.is_active = True
    instance.created_at = datetime.now(timezone.utc)
    instance.last_login_at = None


@pytest.mark.asyncio
async def test_list_admin_users(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    mock_db.execute.return_value = make_list_result([])
    resp = await client.get("/api/v1/admin-users")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_admin_users_manager_forbidden(client, mock_db):
    resp = await client.get("/api/v1/admin-users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_admin_user(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    new_id = uuid.uuid4()

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": str(new_id)}

    mock_db.refresh = AsyncMock(side_effect=_populate_admin_user)

    with patch("app.api.admin_users.httpx.AsyncClient") as mock_client_cls:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        resp = await client.post("/api/v1/admin-users", json={
            "email": "new@test.com",
            "password": "Str0ngPass!",
            "role": "staff",
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_admin_user(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    user = _make_admin_user()
    mock_db.execute.return_value = make_scalar_result(user)
    mock_db.refresh = AsyncMock()

    resp = await client.put(f"/api/v1/admin-users/{user.id}", json={
        "role": "manager",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_admin_user_not_found(client, mock_db, owner_user, auth_as):
    auth_as(owner_user)
    mock_db.execute.return_value = make_scalar_result(None)
    resp = await client.put(f"/api/v1/admin-users/{uuid.uuid4()}", json={
        "role": "manager",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_users_no_auth(no_auth_client):
    resp = await no_auth_client.get("/api/v1/admin-users")
    assert resp.status_code in (401, 403)
