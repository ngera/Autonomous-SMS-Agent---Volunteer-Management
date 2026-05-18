"""Service-eligibility checks for recruitment targeting.

A volunteer is eligible for a service when either:
- ``Contact.all_services_enabled`` is True, OR
- a row exists in ``contact_preferred_types`` linking this contact to the service.

Centralized here so the recruiter's targeting layer and the admin chat tools
apply the same rule.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.contact_preferred_type import ContactPreferredType


async def eligible_for_service(
    db: AsyncSession,
    contact: Contact,
    appointment_type_id: uuid.UUID,
) -> bool:
    """Return True if the contact is allowed to be solicited for this service."""
    if contact.all_services_enabled:
        return True
    result = await db.execute(
        select(ContactPreferredType.id).where(
            ContactPreferredType.tenant_id == contact.tenant_id,
            ContactPreferredType.contact_id == contact.id,
            ContactPreferredType.appointment_type_id == appointment_type_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def eligible_contact_ids(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    appointment_type_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Return the set of contact_ids eligible for a service in a tenant.

    Includes contacts with ``all_services_enabled`` and contacts with an
    explicit ``ContactPreferredType`` row. Caller is responsible for any
    further filtering (consent, suspension, etc).
    """
    all_enabled = await db.execute(
        select(Contact.id).where(
            Contact.tenant_id == tenant_id,
            Contact.all_services_enabled.is_(True),
        )
    )
    preferred = await db.execute(
        select(ContactPreferredType.contact_id).where(
            ContactPreferredType.tenant_id == tenant_id,
            ContactPreferredType.appointment_type_id == appointment_type_id,
        )
    )
    return set(all_enabled.scalars().all()) | set(preferred.scalars().all())
