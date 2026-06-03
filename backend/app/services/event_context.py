"""Shared helper for assembling SMS-template variable dicts.

Decision #28 / review-pass issue #14: every rich-content reply
(check-in confirmation, check-out, walk-up, no-event, etc.) needs
the same variable dict — name, event_name, service, location,
start_time, end_time, hh_mm, total_hours, etc. Centralizing here
means the field-omission rule ("skip null location, don't render
'Location: None'") is implemented once and reused by every caller.

Timezone assumption: all time-of-day rendering uses Eastern Time
for now. Tenant-timezone-aware rendering is on the backlog (see
event_lifecycle_plan.md fix for review-pass issue #6).
"""
from __future__ import annotations

from datetime import datetime, time as time_obj
from decimal import Decimal
from typing import Any

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

# Eastern Time — fixed assumption for now (backlog: tenant-timezone-aware).
_EASTERN = ZoneInfo("America/New_York")


def _fmt_hh_mm(dt: datetime | None) -> str:
    """Render a datetime as 'H:MM AM/PM' in Eastern Time."""
    if dt is None:
        return ""
    return dt.astimezone(_EASTERN).strftime("%-I:%M %p").lstrip("0")


def _fmt_time(t: time_obj | None) -> str:
    """Render a naive time as 'H:MM AM/PM' (no timezone conversion)."""
    if t is None:
        return ""
    return t.strftime("%-I:%M %p").lstrip("0")


def _omit_if_none(d: dict, keys: list[str]) -> dict:
    """Drop keys whose values are None / empty string from the rendering dict.

    Templates use .format() which fails if a referenced variable is
    missing — for graceful field omission, we substitute empty string.
    """
    out = dict(d)
    for k in keys:
        if out.get(k) in (None, ""):
            out[k] = ""
    return out


def render_event_context(
    *,
    contact: Any | None = None,
    booking: Any | None = None,
    slot: Any | None = None,
    appointment_type: Any | None = None,
    total_hours: Decimal | float | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Assemble the variable dict for a rich SMS-template render.

    Pass whichever inputs are available; missing fields render as empty
    strings (callers can also use the template wording to skip them).

    Returns dict suitable for `template.format(**vars)`. Includes:
      - name, first_name
      - event_name, location, start_time, end_time
      - service (appointment_type name)
      - hh_mm (current time-of-day)
      - total_hours (if provided)
      - any keys passed in `extra`
    """
    out: dict[str, Any] = {
        "name": "",
        "first_name": "",
        "event_name": "",
        "location": "",
        "start_time": "",
        "end_time": "",
        "service": "",
        "hh_mm": _fmt_hh_mm(datetime.now(_EASTERN)),
        "total_hours": "",
    }

    if contact is not None:
        name = getattr(contact, "name", None) or ""
        out["name"] = name
        out["first_name"] = (name.split() or [""])[0]

    if slot is not None:
        out["event_name"] = getattr(slot, "label", None) or ""
        out["location"] = getattr(slot, "location", None) or ""
        out["start_time"] = _fmt_time(getattr(slot, "start_time", None))
        out["end_time"] = _fmt_time(getattr(slot, "end_time", None))

    if appointment_type is not None:
        out["service"] = getattr(appointment_type, "name", None) or ""

    if total_hours is not None:
        if isinstance(total_hours, Decimal):
            out["total_hours"] = f"{total_hours:.2f}"
        else:
            out["total_hours"] = f"{float(total_hours):.2f}"

    if extra:
        out.update(extra)

    return out


__all__ = ["render_event_context"]
