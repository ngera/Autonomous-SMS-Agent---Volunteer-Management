"""Unit tests for the service-eligibility helper."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import eligibility


def _contact(all_services: bool = False):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.tenant_id = uuid.uuid4()
    c.all_services_enabled = all_services
    return c


@pytest.mark.asyncio
async def test_all_services_enabled_short_circuits():
    """When all_services_enabled is True, no DB lookup is needed."""
    db = AsyncMock()
    contact = _contact(all_services=True)

    result = await eligibility.eligible_for_service(db, contact, uuid.uuid4())

    assert result is True
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_preferred_type_row_makes_eligible():
    db = AsyncMock()
    contact = _contact(all_services=False)

    res = MagicMock()
    res.scalar_one_or_none.return_value = uuid.uuid4()
    db.execute.return_value = res

    assert await eligibility.eligible_for_service(db, contact, uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_no_preferred_row_and_not_all_enabled_is_ineligible():
    db = AsyncMock()
    contact = _contact(all_services=False)

    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    db.execute.return_value = res

    assert await eligibility.eligible_for_service(db, contact, uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_eligible_contact_ids_unions_both_sources():
    """Union of all_services_enabled set and preferred-type set."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    service_id = uuid.uuid4()

    all_enabled = [uuid.uuid4(), uuid.uuid4()]
    preferred = [uuid.uuid4(), all_enabled[0]]  # overlap on first id

    def _result(items):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items
        return r

    db.execute.side_effect = [_result(all_enabled), _result(preferred)]

    result = await eligibility.eligible_contact_ids(db, tenant_id, service_id)

    assert result == set(all_enabled) | set(preferred)
    assert len(result) == 3  # one overlap deduped
