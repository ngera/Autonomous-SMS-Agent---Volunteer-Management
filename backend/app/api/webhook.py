"""Twilio SMS webhook endpoint.

Receives inbound SMS, validates signature, returns 200 immediately,
then processes the message asynchronously in a background task.

Multi-tenant: resolves tenant from the `To` phone number (each tenant
has a unique twilio_phone_number).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.tenant import Tenant
from app.modules.pipeline import process_inbound_message
from app.services.sms import validate_twilio_signature

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])
logger = get_logger("webhook")


@router.post("/sms")
async def receive_sms(request: Request, background_tasks: BackgroundTasks):
    """Receive inbound SMS from Twilio.

    Steps 1-4 of the pipeline:
    1. Twilio POSTs to this endpoint
    2. Resolve tenant from `To` phone number
    3. Validate X-Twilio-Signature using tenant's auth token
    4. Return 200 immediately, process message asynchronously
    """
    # Parse form data
    form_data = await request.form()
    params = dict(form_data)

    to_phone = params.get("To", "")
    from_phone = params.get("From", "")
    message_body = params.get("Body", "")
    message_type = params.get("NumMedia", "0")

    # Step 2: Resolve tenant from the `To` phone number
    async with async_session_factory() as db:
        tenant_result = await db.execute(
            select(Tenant).where(
                Tenant.twilio_phone_number == to_phone,
                Tenant.is_active.is_(True),
            )
        )
        tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        logger.warning("No active tenant found for To number: %s", to_phone)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown destination number",
        )

    tenant_id = tenant.id

    # Step 3: Validate Twilio signature using tenant's auth token
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    if not validate_twilio_signature(url, params, signature, tenant=tenant):
        logger.warning(
            "Invalid Twilio signature from %s for tenant %s",
            request.client.host if request.client else "unknown",
            tenant.slug,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    if not from_phone or not message_body:
        logger.warning("Received SMS with missing From or Body")
        return {"status": "ignored"}

    # Handle non-text messages (images, audio, etc.)
    if int(message_type) > 0:
        background_tasks.add_task(
            _send_media_redirect, from_phone, tenant_id
        )
        return {"status": "accepted"}

    logger.info(
        "Inbound SMS from %s to tenant %s (%d chars)",
        from_phone, tenant.slug, len(message_body),
    )

    # Step 4: Return 200 immediately, process in background
    background_tasks.add_task(
        _process_message_background, from_phone, message_body, tenant_id
    )

    return {"status": "accepted"}


async def _process_message_background(
    from_phone: str, message_body: str, tenant_id: uuid.UUID,
) -> None:
    """Process an inbound message in a background task with its own DB session."""
    try:
        async with async_session_factory() as db:
            try:
                await process_inbound_message(
                    db, from_phone, message_body, tenant_id=tenant_id,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    except Exception as e:
        logger.error("Pipeline error for %s: %s", from_phone, str(e), exc_info=True)


async def _send_media_redirect(phone: str, tenant_id: uuid.UUID) -> None:
    """Send a polite redirect for non-text messages."""
    from app.services.sms import send_sms

    # Load tenant for SMS credentials
    async with async_session_factory() as db:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

    await send_sms(
        to=phone,
        body="I can only process text messages. Please send your request as a text message.",
        tenant=tenant,
    )
