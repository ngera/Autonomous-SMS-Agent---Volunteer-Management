"""Layer 2 — Intent classifier eval.

Each case is an admin SMS; target is the expected intent string. We
invoke the production classifier (`app.agents.orchestrator.intent_classifier.classify`)
which calls Haiku 4.5 under the hood. Scorer is structural: intent
equality + substring match on event_reference.

Gating: overall accuracy must not drop more than 2pp from baseline.
Baseline is captured the first time the suite runs green on master.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    PARTIAL,
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


@solver
def classifier_solver():
    """Calls the production classifier. DB + Tenant are passed as
    lightweight mocks since the classifier only needs them for
    audit logging — it doesn't query state."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        from unittest.mock import AsyncMock, MagicMock

        from app.agents.orchestrator.intent_classifier import classify  # type: ignore

        fake_db = MagicMock()
        fake_db.add = MagicMock()
        fake_db.commit = AsyncMock()
        fake_tenant = MagicMock()
        fake_tenant.id = "00000000-0000-0000-0000-000000000000"
        fake_tenant.anthropic_api_key = None  # falls through to env

        decision = await classify(state.input_text, fake_db, fake_tenant)
        if decision is None:
            state.output.completion = "other"
            state.metadata["confidence"] = 0.0
            state.metadata["event_reference"] = None
        else:
            state.output.completion = decision.intent
            state.metadata["confidence"] = decision.confidence
            state.metadata["event_reference"] = decision.event_reference
        return state

    return solve


@scorer(metrics=[accuracy()])
def intent_match():
    async def score(state: TaskState, target: Target) -> Score:
        got_intent = (state.output.completion or "").strip()
        want_intent = target.text.strip()
        if got_intent != want_intent:
            return Score(
                value=INCORRECT,
                explanation=f"expected intent={want_intent}, got {got_intent}",
            )

        # Soft check on event_reference if specified.
        expected_ref = (state.metadata or {}).get("expected_event_reference")
        got_ref = (state.metadata or {}).get("event_reference") or ""
        if expected_ref and expected_ref.lower() not in got_ref.lower():
            return Score(
                value=PARTIAL,
                explanation=(
                    f"intent ok ({got_intent}) but event_reference miss: "
                    f"expected substring '{expected_ref}', got '{got_ref}'"
                ),
            )

        # Confidence floor check.
        floor = (state.metadata or {}).get("confidence_floor")
        got_conf = (state.metadata or {}).get("confidence", 0.0)
        if floor is not None and got_conf < floor:
            return Score(
                value=PARTIAL,
                explanation=f"intent ok but confidence {got_conf:.2f} < floor {floor}",
            )

        return Score(value=CORRECT, explanation=f"intent={got_intent}")

    return score


@task
def intent_classification() -> Task:
    return Task(
        dataset=json_dataset(
            str(Path(__file__).parent.parent / "datasets" / "intent_classifier.jsonl")
        ),
        solver=classifier_solver(),
        scorer=intent_match(),
    )
