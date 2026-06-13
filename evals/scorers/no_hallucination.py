"""Stub scorer: checks the agent's reply against known DB state to flag
hallucinations.

Real implementation will:
  - Read the case's tenant_seed and pull the expected facts (e.g. service
    list, contact names, event dates) from the seeded DB.
  - Tokenize the agent output and verify that any volunteer name / phone
    / date mentioned is one that actually exists in scope.

For Week 1 this is a stub that always returns CORRECT.
"""
from __future__ import annotations

from inspect_ai.scorer import CORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState


@scorer(metrics=[accuracy()])
def no_hallucination() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        # Phase 2: hook into the seeded DB and verify factual claims.
        return Score(value=CORRECT, explanation="stub — phase 2 will verify against DB facts")

    return score
