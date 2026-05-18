"""Per-tenant rolling-window LLM request rate limiter.

The slowapi-based HTTP rate limit only protects per-IP, which doesn't bound
a single tenant's LLM spend — a runaway loop inside one tenant's session
(e.g., a test harness, a misbehaving integration, an admin clicking a
button repeatedly) can chew through Anthropic credit fast. This module
caps requests-per-minute-per-tenant in-process.

In-memory + asyncio.Lock — fine for a single-instance deployment. For
multi-instance, swap the timestamp dict for a Redis sorted-set with the
same algorithm.

The per-tenant ceiling is configurable from the UI by super-admins via
the ``llm_rate_limit_rpm`` SystemSetting key (Settings → System Settings).
Falls back to ``DEFAULT_PER_TENANT_RPM`` when unset or out of bounds.

See design_decisions.md decision #15.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict, deque
from typing import Deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger("llm_rate_limit")

# How many LLM calls a single tenant may make per rolling 60-second window
# when there's no per-tenant override. Picked to be very loose for normal
# use (planner ~3-6 calls + reporter + admin chats fit comfortably) but
# tight enough to catch runaway loops.
DEFAULT_PER_TENANT_RPM = 60
WINDOW_SECONDS = 60.0

# Safety bounds on the per-tenant override. 10 is the lowest value that
# still allows a planner run + a few admin turns; 1000 is far higher than
# any sane workload but still protective against typos like 99999.
SETTING_KEY = "llm_rate_limit_rpm"
MIN_LIMIT = 10
MAX_LIMIT = 1000


async def get_tenant_limit(
    db: AsyncSession, tenant_id: uuid.UUID | str
) -> int:
    """Return the effective per-minute LLM cap for a tenant.

    Reads ``SystemSetting(key="llm_rate_limit_rpm")`` for the tenant;
    falls back to ``DEFAULT_PER_TENANT_RPM`` when unset, non-numeric, or
    outside the [MIN_LIMIT, MAX_LIMIT] safety bounds. Cheap single-row
    SELECT; safe to call on every LLM request.
    """
    from app.models.system_setting import SystemSetting

    result = await db.execute(
        select(SystemSetting.value).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == SETTING_KEY,
        )
    )
    raw = result.scalar_one_or_none()
    if raw is None:
        return DEFAULT_PER_TENANT_RPM
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PER_TENANT_RPM
    if n < MIN_LIMIT or n > MAX_LIMIT:
        logger.warning(
            "Tenant %s has out-of-bounds llm_rate_limit_rpm=%r; "
            "falling back to default %d",
            tenant_id, raw, DEFAULT_PER_TENANT_RPM,
        )
        return DEFAULT_PER_TENANT_RPM
    return n

# Per-tenant deque of timestamps for calls in the current window.
_buckets: dict[str, Deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


class LLMRateLimitExceeded(Exception):
    """Raised when a tenant has exceeded its per-minute LLM request cap."""

    def __init__(self, tenant_id: uuid.UUID, retry_after_seconds: float):
        self.tenant_id = tenant_id
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Tenant {tenant_id} exceeded LLM rate limit; retry in "
            f"{retry_after_seconds:.1f}s"
        )


async def consume(
    tenant_id: uuid.UUID | str,
    limit: int = DEFAULT_PER_TENANT_RPM,
) -> None:
    """Check + record one LLM call for the tenant.

    Raises ``LLMRateLimitExceeded`` if the cap would be exceeded. Otherwise
    appends the current timestamp and returns. Callers should let the
    exception propagate to the request handler, which can map it to a
    user-friendly response.
    """
    key = str(tenant_id)
    now = time.monotonic()
    cutoff = now - WINDOW_SECONDS

    async with _lock:
        bucket = _buckets[key]
        # Drop timestamps that fall outside the window.
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            oldest = bucket[0]
            retry_after = WINDOW_SECONDS - (now - oldest)
            logger.warning(
                "LLM rate limit hit: tenant=%s used=%d/%d retry_after=%.1fs",
                key, len(bucket), limit, retry_after,
            )
            raise LLMRateLimitExceeded(tenant_id, max(retry_after, 1.0))
        bucket.append(now)


def reset(tenant_id: uuid.UUID | str) -> None:
    """Test/admin helper: clear a tenant's bucket."""
    _buckets.pop(str(tenant_id), None)


def current_usage(tenant_id: uuid.UUID | str) -> int:
    """How many calls the tenant has made in the current window. Diagnostic."""
    key = str(tenant_id)
    bucket = _buckets.get(key)
    if not bucket:
        return 0
    now = time.monotonic()
    cutoff = now - WINDOW_SECONDS
    return sum(1 for t in bucket if t >= cutoff)
