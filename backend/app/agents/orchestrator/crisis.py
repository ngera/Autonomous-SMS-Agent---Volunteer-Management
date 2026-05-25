"""Crisis-language detection on inbound messages.

Phase 1 (Path A): rule-based keyword check only. Phase 2: extends with
a Haiku classifier (resolve_model('orchestrator_crisis')) that detects
distress, self-harm, emergency, threat. On hit:
  - Pauses agent responses for the thread (sets conversations.takeover_mode)
  - Creates a high-priority issue_report (per issue_reporting_plan)
  - Notifies the on-call admin

Today's screener catches IRRELEVANT and ABUSIVE; crisis is a stricter
sibling concept distinct from abuse — a volunteer in crisis is not
abusive but needs immediate human attention.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrisisDecision:
    is_crisis: bool
    severity: str | None  # 'distress' | 'threat' | 'emergency' | None
    reason: str | None


# Rough keyword pre-filter — Phase 2 adds an LLM classifier on top.
# These are deliberately conservative to avoid false positives that
# would auto-pause healthy conversations.
_CRISIS_KEYWORDS = {
    "kill myself", "suicide", "suicidal", "end my life",
    "hurt myself", "self harm", "self-harm",
    "emergency", "911", "help me please",
    "going to die", "want to die",
}


async def check(message: str) -> CrisisDecision:
    """Phase 1: rule-based pre-filter only."""
    normalized = (message or "").strip().lower()
    for kw in _CRISIS_KEYWORDS:
        if kw in normalized:
            return CrisisDecision(
                is_crisis=True,
                severity="distress",
                reason=f"matched-keyword: {kw}",
            )
    return CrisisDecision(is_crisis=False, severity=None, reason=None)
