"""Tests for Twilio SMS webhook endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_webhook_valid_signature(client, mock_db):
    with patch("app.api.webhook.validate_twilio_signature", return_value=True), \
         patch("app.api.webhook._process_message_background", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/webhook/sms",
            data={"From": "+447700900000", "Body": "Hello", "NumMedia": "0"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_webhook_invalid_signature(client, mock_db):
    with patch("app.api.webhook.validate_twilio_signature", return_value=False):
        resp = await client.post(
            "/api/v1/webhook/sms",
            data={"From": "+447700900000", "Body": "Hello"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_missing_body(client, mock_db):
    with patch("app.api.webhook.validate_twilio_signature", return_value=True):
        resp = await client.post(
            "/api/v1/webhook/sms",
            data={"From": "+447700900000", "Body": "", "NumMedia": "0"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
