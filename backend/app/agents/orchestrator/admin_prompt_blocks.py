"""Admin LLM context-block renderers (decision #28 category II).

Two prompt entries don't render directly into SMS bodies — they get
injected into the admin LLM's system prompt at request time, with
dynamic data substituted in:

  - prompt_admin_live_events_context_block
      Lists currently live events + their check-in counts.
      Empty when no events are live (block not appended).

  - prompt_admin_personal_bookings_context_block
      Lists the admin's own bookings on their auto-linked Contact.
      Empty when admin has no active/upcoming bookings.

Both renderers are wrapped in TTL caches because admin chat during
day-of operations can fire 10-20 LLM calls per minute; uncached
queries on every call would amplify DB load. Cache invalidation on
writes (CHECKIN/CHECKOUT/RESERVE/APPROVE/REJECT) keeps state fresh
via explicit eviction helpers.

Decision #28 (category II) + decision #29(a/b/c) caching add.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser
from app.models.availability import SpecificDateSlot
from app.models.booking import Booking, BookingStatus
from app.models.contact import Contact
from app.prompts.conversation import (
    PROMPT_ADMIN_LIVE_EVENTS_CONTEXT_BLOCK,
    PROMPT_ADMIN_PERSONAL_BOOKINGS_CONTEXT_BLOCK,
)


# ── Caches ──────────────────────────────────────────────────────────
# 30s TTL matches the dashboard / run-sheet polling cadence elsewhere
# in the plan. Admins already accustomed to 30s freshness across the
# system; the LLM responding from the same window is a feature.

_LIVE_EVENTS_CACHE: TTLCache = TTLCache(maxsize=512, ttl=30)
_PERSONAL_BOOKINGS_CACHE: TTLCache = TTLCache(maxsize=2048, ttl=60)
_CACHE_LOCK = asyncio.Lock()


def evict_live_events_cache(tenant_id: uuid.UUID) -> None:
    """Drop the live-events block for a tenant. Called after CHECKIN /
    CHECKOUT / RESERVE / APPROVE / REJECT mutations so the next render
    reflects the change."""
    _LIVE_EVENTS_CACHE.pop(str(tenant_id), None)


def evict_personal_bookings_cache(admin_id: uuid.UUID) -> None:
    """Drop the personal-bookings block for a specific admin."""
    _PERSONAL_BOOKINGS_CACHE.pop(str(admin_id), None)


# ── Renderers ───────────────────────────────────────────────────────

def _format_slot_line(idx: int, slot: SpecificDateSlot, checked_in: int, total: int) -> str:
    """Format one row in the live-events context block."""
    name = slot.label or "(unnamed event)"
    start = slot.start_time.strftime("%I:%M %p").lstrip("0")
    end = slot.end_time.strftime("%I:%M %p").lstrip("0")
    return f"{idx}) {name} ({start} – {end}, {checked_in}/{total} checked in)"


async def _query_live_slots_with_counts(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[tuple[SpecificDateSlot, int, int]]:
    """Return [(slot, checked_in_count, total_bookings), ...] for slots in
    the live window."""
    from app.services.event_eligibility import _slot_in_live_window

    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(SpecificDateSlot).where(
            SpecificDateSlot.tenant_id == tenant_id,
            SpecificDateSlot.is_active.is_(True),
            SpecificDateSlot.date.between(
                today - timedelta(days=1), today + timedelta(days=1)
            ),
        )
    )
    now_utc = datetime.now(timezone.utc)
    rows: list[tuple[SpecificDateSlot, int, int]] = []
    for slot in result.scalars().all():
        if not _slot_in_live_window(slot, now_utc):
            continue
        bookings_result = await db.execute(
            select(Booking).where(
                Booking.event_slot_id == slot.id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
        bookings = bookings_result.scalars().all()
        total = len(bookings)
        checked_in = sum(1 for b in bookings if b.checked_in_at is not None)
        rows.append((slot, checked_in, total))
    return rows


async def render_live_events_block(
    db: AsyncSession, tenant_id: uuid.UUID
) -> str:
    """Return the formatted live-events context block, or empty string
    if no events are live.

    Cached per-tenant with 30s TTL. Eviction on admin write paths
    (CHECKIN / CHECKOUT / RESERVE / APPROVE / REJECT) keeps state fresh.
    """
    cache_key = str(tenant_id)
    async with _CACHE_LOCK:
        if cache_key in _LIVE_EVENTS_CACHE:
            return _LIVE_EVENTS_CACHE[cache_key]

    rows = await _query_live_slots_with_counts(db, tenant_id)
    if not rows:
        async with _CACHE_LOCK:
            _LIVE_EVENTS_CACHE[cache_key] = ""
        return ""

    event_list = "\n".join(
        _format_slot_line(i + 1, slot, checked_in, total)
        for i, (slot, checked_in, total) in enumerate(rows)
    )
    rendered = PROMPT_ADMIN_LIVE_EVENTS_CONTEXT_BLOCK.format(event_list=event_list)
    async with _CACHE_LOCK:
        _LIVE_EVENTS_CACHE[cache_key] = rendered
    return rendered


async def render_personal_bookings_block(
    db: AsyncSession, admin: AdminUser
) -> str:
    """Return the admin's personal-bookings context block, or empty
    string if admin has no linked Contact or no active/upcoming
    bookings.

    Cached per-admin with 60s TTL.
    """
    if admin.tenant_id is None:
        return ""

    cache_key = str(admin.id)
    async with _CACHE_LOCK:
        if cache_key in _PERSONAL_BOOKINGS_CACHE:
            return _PERSONAL_BOOKINGS_CACHE[cache_key]

    # Find the admin's linked Contact.
    contact_result = await db.execute(
        select(Contact).where(Contact.admin_user_id == admin.id)
    )
    contact = contact_result.scalar_one_or_none()
    if contact is None:
        async with _CACHE_LOCK:
            _PERSONAL_BOOKINGS_CACHE[cache_key] = ""
        return ""

    # Active/upcoming bookings on this contact.
    now_utc = datetime.now(timezone.utc)
    bookings_result = await db.execute(
        select(Booking)
        .where(
            Booking.contact_id == contact.id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.scheduled_at >= now_utc - timedelta(hours=24),
        )
        .order_by(Booking.scheduled_at)
    )
    bookings = bookings_result.scalars().all()
    if not bookings:
        async with _CACHE_LOCK:
            _PERSONAL_BOOKINGS_CACHE[cache_key] = ""
        return ""

    lines = []
    for i, b in enumerate(bookings, 1):
        when = b.scheduled_at.strftime("%a %b %d at %I:%M %p").lstrip("0")
        state = "checked in" if b.checked_in_at else "not checked in"
        lines.append(f"{i}) {when} ({state})")
    personal_booking_list = "\n".join(lines)
    rendered = PROMPT_ADMIN_PERSONAL_BOOKINGS_CONTEXT_BLOCK.format(
        personal_booking_list=personal_booking_list
    )
    async with _CACHE_LOCK:
        _PERSONAL_BOOKINGS_CACHE[cache_key] = rendered
    return rendered


__all__ = [
    "render_live_events_block",
    "render_personal_bookings_block",
    "evict_live_events_cache",
    "evict_personal_bookings_cache",
]
