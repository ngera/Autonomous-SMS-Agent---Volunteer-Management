from datetime import datetime, timedelta

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _get_credentials() -> Credentials:
    """Build Google OAuth2 credentials from stored refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=settings.google_refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(GoogleRequest())
    return creds


def _get_service():
    """Build the Google Calendar API service client."""
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


async def get_busy_periods(
    time_min: datetime, time_max: datetime
) -> list[dict]:
    """Query Google Calendar freeBusy API for busy periods.

    Returns list of {"start": datetime_str, "end": datetime_str}.
    """
    try:
        service = _get_service()
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": "primary"}],
        }
        result = service.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
        logger.info("Retrieved %d busy periods from Google Calendar", len(busy))
        return busy
    except Exception as e:
        logger.error("Google Calendar freeBusy error: %s", str(e))
        raise


async def create_event(
    summary: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
) -> str:
    """Create a Google Calendar event. Returns the event ID."""
    try:
        service = _get_service()
        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": settings.business_timezone,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": settings.business_timezone,
            },
        }
        result = service.events().insert(calendarId="primary", body=event).execute()
        event_id = result["id"]
        logger.info("Created calendar event: %s", event_id)
        return event_id
    except Exception as e:
        logger.error("Google Calendar create event error: %s", str(e))
        raise


async def update_event(
    event_id: str,
    start_time: datetime,
    end_time: datetime,
    summary: str | None = None,
    description: str | None = None,
) -> None:
    """Update an existing Google Calendar event."""
    try:
        service = _get_service()
        body = {
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": settings.business_timezone,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": settings.business_timezone,
            },
        }
        if summary:
            body["summary"] = summary
        if description:
            body["description"] = description

        service.events().patch(
            calendarId="primary", eventId=event_id, body=body
        ).execute()
        logger.info("Updated calendar event: %s", event_id)
    except Exception as e:
        logger.error("Google Calendar update event error: %s", str(e))
        raise


async def delete_event(event_id: str) -> None:
    """Delete a Google Calendar event."""
    try:
        service = _get_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        logger.info("Deleted calendar event: %s", event_id)
    except Exception as e:
        logger.error("Google Calendar delete event error: %s", str(e))
        raise
