"""Stub scorer: uses prompt rubric for "mustr voice" — warm, brief,
gives an out, no marketing speak.

Delegates to llm_as_judge_sms with the `on_brand_voice` rubric in Phase 2.
"""
from __future__ import annotations

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState


@scorer(metrics=[mean()])
def on_brand_voice() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        # Phase 2: rubric exists; just delegate to llm_as_judge_sms("on_brand_voice").
        return Score(value=5.0, explanation="stub — phase 2 will run the on_brand_voice rubric")

    return score
