import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
from app.models.notification import AdminNotification, NotificationType
from app.models.tenant import Tenant
from app.services.sms import send_sms

logger = get_logger("notification")


async def create_notification(
    db: AsyncSession,
    notification_type: NotificationType,
    title: str,
    body: str,
    tenant_id: uuid.UUID | None = None,
    reference_id: uuid.UUID | None = None,
    reference_type: str | None = None,
    admin_user_id: uuid.UUID | None = None,
) -> AdminNotification:
    """Create an in-app notification. If admin_user_id is None, it broadcasts to all."""
    notification = AdminNotification(
        tenant_id=tenant_id,
        admin_user_id=admin_user_id,
        type=notification_type,
        title=title,
        body=body,
        reference_id=reference_id,
        reference_type=reference_type,
    )
    db.add(notification)
    await db.flush()
    return notification


async def notify_suspension(
    db: AsyncSession,
    contact_phone: str,
    suspension_id: uuid.UUID,
    reason: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Create in-app notification + send email + SMS to all Owners and Managers on suspension."""
    logger.info("[SUSPENSION NOTIFY] Starting for contact=%s tenant=%s", contact_phone, tenant_id)

    # Look up volunteer name
    from app.models.contact import Contact
    contact_query = select(Contact.name).where(Contact.phone == contact_phone)
    if tenant_id:
        contact_query = contact_query.where(Contact.tenant_id == tenant_id)
    contact_result = await db.execute(contact_query)
    contact_name = contact_result.scalar_one_or_none() or "Unknown"
    display_name = f"{contact_name} ({contact_phone})"

    # In-app notification (broadcast)
    await create_notification(
        db=db,
        notification_type=NotificationType.ACCOUNT_SUSPENDED,
        title=f"Account suspended: {display_name}",
        body=f"Reason: {reason}",
        tenant_id=tenant_id,
        reference_id=suspension_id,
        reference_type="suspension",
    )
    logger.info("[SUSPENSION NOTIFY] In-app notification created")

    # Email notification to owners and managers
    admin_filters = [
        AdminUser.is_active.is_(True),
        AdminUser.role.in_([AdminRole.OWNER, AdminRole.MANAGER]),
    ]
    if tenant_id:
        admin_filters.append(AdminUser.tenant_id == tenant_id)
    result = await db.execute(
        select(AdminUser).where(*admin_filters)
    )
    admins = result.scalars().all()
    logger.info("[SUSPENSION NOTIFY] Found %d admin(s) to notify", len(admins))

    # Load tenant for email credentials
    tenant = None
    if tenant_id:
        from app.models.tenant import Tenant as TenantModel
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        logger.warning("[SUSPENSION NOTIFY] No tenant loaded — skipping email/SMS")
        return

    logger.info(
        "[SUSPENSION NOTIFY] Tenant credentials: has_resend_key=%s from_email=%s",
        bool(tenant.resend_api_key),
        tenant.resend_from_email or "(none)",
    )

    for admin in admins:
        # Email notification
        logger.info("[SUSPENSION NOTIFY] Attempting email to admin=%s", admin.email)
        email_sent = await send_email(
            to=admin.email,
            subject=f"[URGENT] Account Suspended: {display_name}",
            html=f"""
            <h2>Account Suspended</h2>
            <p><strong>Volunteer:</strong> {display_name}</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>Please review this suspension in the admin panel.</p>
            """,
            tenant=tenant,
        )
        logger.info(
            "[SUSPENSION NOTIFY] Email to %s result: %s",
            admin.email,
            "SENT" if email_sent else "FAILED/SKIPPED",
        )

        # SMS notification to admins who have a phone number
        if admin.phone and tenant:
            logger.info("[SUSPENSION NOTIFY] Attempting SMS to admin phone=%s", admin.phone)
            sms_sid = await send_sms(
                to=admin.phone,
                body=f"[ALERT] Account suspended: {display_name}. Reason: {reason}. Please review in admin panel.",
                tenant=tenant,
            )
            logger.info(
                "[SUSPENSION NOTIFY] SMS to %s result: %s",
                admin.phone,
                f"SENT sid={sms_sid}" if sms_sid else "FAILED",
            )
        else:
            logger.info(
                "[SUSPENSION NOTIFY] Skipping SMS for admin=%s (no phone set)",
                admin.email,
            )

    logger.info("[SUSPENSION NOTIFY] Complete for contact=%s", contact_phone)


async def send_email(
    to: str, subject: str, html: str, tenant: Tenant | None = None
) -> bool:
    """Send an email via Resend API."""
    resend_api_key = tenant.resend_api_key if tenant else None
    resend_from_email = tenant.resend_from_email if tenant else None

    if not resend_api_key:
        logger.warning("[EMAIL] Resend API key not configured, skipping email to %s", to)
        return False

    if not resend_from_email:
        logger.warning("[EMAIL] Resend from_email not configured, skipping email to %s", to)
        return False

    logger.info("[EMAIL] Sending via Resend: from=%s to=%s subject=%s", resend_from_email, to, subject)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json={
                    "from": resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

        if response.status_code in (200, 201):
            try:
                msg_id = response.json().get("id", "unknown")
            except Exception:
                msg_id = "unknown"
            logger.info("[EMAIL] SUCCESS to=%s id=%s subject=%s", to, msg_id, subject)
            return True

        logger.warning(
            "[EMAIL] Resend API error: status=%d body=%s (from=%s to=%s)",
            response.status_code, response.text[:300], resend_from_email, to,
        )
        return False

    except httpx.RequestError as e:
        logger.error("[EMAIL] Request exception sending to %s: %s", to, str(e))
        return False
    except Exception as e:
        logger.error("[EMAIL] Unexpected exception sending to %s: %s", to, str(e), exc_info=True)
        return False
