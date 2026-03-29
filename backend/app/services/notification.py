import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin_user import AdminRole, AdminUser
from app.models.notification import AdminNotification, NotificationType
from app.models.tenant import Tenant

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
    """Create in-app notification + send email to all Owners and Managers on suspension."""
    # In-app notification (broadcast)
    await create_notification(
        db=db,
        notification_type=NotificationType.ACCOUNT_SUSPENDED,
        title=f"Account suspended: {contact_phone}",
        body=f"Reason: {reason}",
        tenant_id=tenant_id,
        reference_id=suspension_id,
        reference_type="suspension",
    )

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

    # Load tenant for email credentials
    tenant = None
    if tenant_id:
        from app.models.tenant import Tenant as TenantModel
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

    for admin in admins:
        await send_email(
            to=admin.email,
            subject=f"[URGENT] Account Suspended: {contact_phone}",
            html=f"""
            <h2>Account Suspended</h2>
            <p><strong>Phone:</strong> {contact_phone}</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>Please review this suspension in the admin panel.</p>
            """,
            tenant=tenant,
        )


async def send_email(
    to: str, subject: str, html: str, tenant: Tenant | None = None
) -> bool:
    """Send an email via Resend API."""
    resend_api_key = tenant.resend_api_key if tenant else None
    resend_from_email = tenant.resend_from_email if tenant else None

    if not resend_api_key:
        logger.warning("Resend API key not configured for tenant, skipping email to %s", to)
        return False

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
            logger.info("Email sent to %s: %s", to, subject)
            return True

        logger.warning("Resend API error: %d %s", response.status_code, response.text[:200])
        return False

    except httpx.RequestError as e:
        logger.error("Failed to send email to %s: %s", to, str(e))
        return False
