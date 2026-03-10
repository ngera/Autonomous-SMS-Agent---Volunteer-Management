"""Tests for auth endpoints."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_login_success(client):
    fake_tokens = {
        "access_token": "fake-access",
        "refresh_token": "fake-refresh",
        "token_type": "bearer",
        "expires_in": 3600,
    }
    with patch("app.api.auth.authenticate_user", new_callable=AsyncMock, return_value=fake_tokens):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "password123",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "fake-access"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    with patch("app.api.auth.authenticate_user", new_callable=AsyncMock, side_effect=ValueError("Invalid credentials")):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "bad@test.com",
            "password": "wrong",
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    fake_tokens = {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "token_type": "bearer",
        "expires_in": 3600,
    }
    with patch("app.api.auth.refresh_access_token", new_callable=AsyncMock, return_value=fake_tokens):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "old-refresh",
        })
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "new-access"


@pytest.mark.asyncio
async def test_logout(client):
    with patch("app.api.auth.logout_user", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert "Logged out" in resp.json()["message"]


@pytest.mark.asyncio
async def test_logout_no_auth(no_auth_client):
    resp = await no_auth_client.post("/api/v1/auth/logout")
    assert resp.status_code in (401, 403)
