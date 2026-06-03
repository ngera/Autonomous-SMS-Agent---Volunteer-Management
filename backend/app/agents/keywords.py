"""Central reserved-keyword registry for SMS commands.

Decision #25 (event_lifecycle_plan.md): all SMS keywords used by
the system (volunteer-side intents, admin-side commands, consent-flow
vocabulary, and carrier-mandated keywords) register here. At module
import the registry asserts uniqueness across categories. Future
features adding a keyword MUST register it here so collisions are
caught at startup, not in production.

Also exposes:
  - CHECKIN_INTENT_REGEX — fast regex used by the webhook pipeline
    (Row 4/5) to decide whether to fire an admin notification for an
    unknown phone signal. Narrower than the full intent classifier;
    false negatives just suppress a borderline-phrased notification
    (review-pass A2 — avoids hoisting the engagement-agent intent
    router earlier in the pipeline).
"""
from __future__ import annotations

import re
from typing import FrozenSet

# ── Categories ──────────────────────────────────────────────────────

# Carrier-reserved (TCPA / industry standard). Never reassignable.
CARRIER_RESERVED: FrozenSet[str] = frozenset({"STOP", "HELP", "START"})

# Existing consent flow (matched case-insensitively by app/modules/pipeline.py).
CONSENT_FLOW: FrozenSet[str] = frozenset({"YES", "NO"})

# Volunteer-side intents (Rows 1-3 of the inbound SMS routing matrix).
VOLUNTEER_INTENTS: FrozenSet[str] = frozenset({
    # Row 1 check-in family
    "HERE", "ARRIVED", "I'M HERE", "CHECKED IN", "AT THE SITE",
    # Row 1 check-out family
    "DONE", "LEAVING", "HEADING OUT", "CHECKING OUT", "FINISHED",
    # Row 1 re-entry confirmation (Edge C)
    "HERE-AGAIN", "BACK",
    # Row 1 multi-booking picker (Edge A)
    "BOTH",  # exactly 2 live bookings
    "ALL",   # 3+ live bookings
    # Row 3 discovery keywords
    "EVENTS", "BOOKINGS",
    # Mid-event service-log intents (Phase 3 wires them up; Phase 1
    # registers them so the collision check is comprehensive)
    "SWITCH", "ALSO",
})

# Admin-side commands (Row 6).
ADMIN_COMMANDS: FrozenSet[str] = frozenset({
    "CHECKIN", "CHECKOUT",
    "CHECKIN ME", "CHECKOUT ME",
    "STATUS",
    "STOP STATUS", "STOP STATUS ALL",
    "APPROVE", "REJECT",
    "RESERVE",
    # Mid-flow escape — clears pending_intent (RESERVE picker, etc.)
    "CANCEL",
})


# ── Collision check (runs at import) ────────────────────────────────

_ALL_CATEGORIES = [
    ("CARRIER_RESERVED", CARRIER_RESERVED),
    ("CONSENT_FLOW", CONSENT_FLOW),
    ("VOLUNTEER_INTENTS", VOLUNTEER_INTENTS),
    ("ADMIN_COMMANDS", ADMIN_COMMANDS),
]


def _assert_no_collisions() -> None:
    """Abort module import if any keyword appears in two categories."""
    seen: dict[str, str] = {}
    for cat_name, keywords in _ALL_CATEGORIES:
        for kw in keywords:
            existing = seen.get(kw)
            if existing is not None:
                raise RuntimeError(
                    f"SMS keyword collision: '{kw}' registered in both "
                    f"{existing!r} and {cat_name!r}. Resolve before app start."
                )
            seen[kw] = cat_name


_assert_no_collisions()


# ── Lightweight regex helpers ───────────────────────────────────────

# Used by the webhook pipeline to gate the Row 4 admin notification
# (cheap, deterministic, no engagement-agent imports — see review-pass A2).
# Matches the explicit HERE-family keywords case-insensitively, with
# optional surrounding whitespace / punctuation.
CHECKIN_INTENT_REGEX = re.compile(
    r"\b(here|i'?m\s+here|arrived|checked\s+in|at\s+the\s+site)\b",
    re.IGNORECASE,
)

# Used by the engagement agent's check-out intent router.
CHECKOUT_INTENT_REGEX = re.compile(
    r"\b(done|leaving|heading\s+out|checking\s+out|finished)\b",
    re.IGNORECASE,
)

# Helper for normalizing inbound messages before category lookup.
def normalize_keyword(text: str) -> str:
    """Strip + uppercase a message for exact-match keyword lookup.

    Used by intent routers that match the full message against
    a known keyword (e.g. bare 'STATUS', 'YES', 'BOTH'). NOT used
    for substring matching like CHECKIN_INTENT_REGEX.
    """
    return (text or "").strip().upper()
