"""Twilio SMS webhook endpoint.

Receives inbound SMS, validates signature, returns 200 immediately,
then processes the message asynchronously in a background task.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.modules.pipeline import process_inbound_message
from app.services.sms import validate_twilio_signature

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])
logger = get_logger("webhook")


@router.post("/sms")
async def receive_sms(request: Request, background_tasks: BackgroundTasks):
    """Receive inbound SMS from Twilio.

    Steps 1-4 of the pipeline:
    1. Twilio POSTs to this endpoint
    2. Validate X-Twilio-Signature
    3. Return 200 immediately
    4. Process message asynchronously
    """
    # Parse form data
    form_data = await request.form()
    params = dict(form_data)

    # Step 2: Validate Twilio signature
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    if not validate_twilio_signature(url, params, signature):
        logger.warning(
            "Invalid Twilio signature from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    from_phone = params.get("From", "")
    message_body = params.get("Body", "")
    message_type = params.get("NumMedia", "0")

    if not from_phone or not message_body:
        logger.warning("Received SMS with missing From or Body")
        return {"status": "ignored"}

    # Handle non-text messages (images, audio, etc.)
    if int(message_type) > 0:
        background_tasks.add_task(
            _send_media_redirect, from_phone
        )
        return {"status": "accepted"}

    logger.info("Inbound SMS from %s (%d chars)", from_phone, len(message_body))

    # Step 3-4: Return 200 immediately, process in background
    background_tasks.add_task(
        _process_message_background, from_phone, message_body
    )

    return {"status": "accepted"}


async def _process_message_background(from_phone: str, message_body: str) -> None:
    """Process an inbound message in a background task with its own DB session."""
    try:
        async with async_session_factory() as db:
            try:
                await process_inbound_message(db, from_phone, message_body)
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    except Exception as e:
        logger.error("Pipeline error for %s: %s", from_phone, str(e), exc_info=True)


async def _send_media_redirect(phone: str) -> None:
    """Send a polite redirect for non-text messages."""
    from app.services.sms import send_sms

    await send_sms(
        to=phone,
        body="I can only process text messages. Please send your request as a text message.",
    )
