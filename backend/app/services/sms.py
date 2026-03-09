import asyncio

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("sms")

TWILIO_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
MAX_RETRIES = 3
BACKOFF_DELAYS = [1, 2, 4]


async def send_sms(to: str, body: str) -> str | None:
    """Send an SMS via Twilio with exponential backoff retry.

    Returns the message SID on success, None on failure.
    """
    payload = {
        "To": to,
        "From": settings.twilio_phone_number,
        "Body": body,
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    TWILIO_API_URL,
                    data=payload,
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                    timeout=10.0,
                )

            if response.status_code in (200, 201):
                data = response.json()
                sid = data.get("sid", "unknown")
                logger.info("SMS sent to %s (SID: %s)", to, sid)
                return sid

            logger.warning(
                "Twilio API error (attempt %d/%d): %d %s",
                attempt + 1, MAX_RETRIES, response.status_code, response.text[:200],
            )

        except httpx.RequestError as e:
            logger.warning(
                "Twilio request error (attempt %d/%d): %s",
                attempt + 1, MAX_RETRIES, str(e),
            )

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(BACKOFF_DELAYS[attempt])

    logger.error("Failed to send SMS to %s after %d attempts", to, MAX_RETRIES)
    return None


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Validate Twilio webhook signature using HMAC-SHA1."""
    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, params, signature)
