"""Layer 1 — Regex router eval.

Runs each case through the actual production regex patterns in
`app.agents.recruiter.chat_tools` and asserts the right pattern set
matched (or no-match for negatives).

No model calls. ~150 cases target; ships with ~6 seed cases.
"""
from __future__ import annotations

import sys
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import Generate, TaskState, solver

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _classify_regex(message: str) -> str:
    """Map a message to the highest-priority matching pattern bucket.

    Priority follows the production routing order: explicit > bare >
    pronoun-subject > no_match.
    """
    from app.agents.recruiter.chat_tools import (  # type: ignore
        _BARE_START_CAMPAIGN_PATTERNS,
        _DELETE_CAMPAIGN_PATTERNS,
        _DELETE_PRONOUN_SUBJECTS,
        _LIST_EVENTS_PATTERNS,
        _START_CAMPAIGN_PATTERNS,
    )

    text = message.strip().lower()

    for pat in _START_CAMPAIGN_PATTERNS:
        if pat.match(text):
            return "start_campaign"
    for pat in _BARE_START_CAMPAIGN_PATTERNS:
        if pat.match(text):
            return "start_campaign_bare"
    for pat in _DELETE_CAMPAIGN_PATTERNS:
        m = pat.match(text)
        if m:
            # Group 1 is the subject phrase (or absent for bare-pronoun
            # patterns). Pronoun-subject set matches the literal subject,
            # not a substring of the whole message — see chat_tools
            # _DELETE_PRONOUN_SUBJECTS semantics.
            subject = (m.group(1) if m.groups() else "").strip(" .!?,;:") if m.groups() else ""
            if subject in _DELETE_PRONOUN_SUBJECTS:
                return "delete_campaign_pronoun"
            return "delete_campaign"
    for pat in _LIST_EVENTS_PATTERNS:
        if pat.match(text):
            return "list_events"

    return "no_match"


@solver
def regex_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        bucket = _classify_regex(state.input_text)
        state.output.completion = bucket
        return state

    return solve


@scorer(metrics=[accuracy()])
def exact_match():
    async def score(state: TaskState, target: Target) -> Score:
        got = (state.output.completion or "").strip()
        want = target.text.strip()
        if got == want:
            return Score(value=CORRECT, explanation=f"matched {got}")
        return Score(value=INCORRECT, explanation=f"expected {want}, got {got}")

    return score


@task
def regex_routing() -> Task:
    return Task(
        dataset=json_dataset(
            str(Path(__file__).parent.parent / "datasets" / "regex_router.jsonl")
        ),
        solver=regex_solver(),
        scorer=exact_match(),
    )
