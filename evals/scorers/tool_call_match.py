"""Structural scorer: did the agent call the expected tools with the
expected args, and avoid the forbidden ones?

Reads `expected_tools`, `must_NOT_call`, `must_have` from sample metadata.
Returns CORRECT only if every expected tool was called (in any order) with
all `must_have` args present, AND no forbidden tool was called.

The agent's tool-call trace is expected on `state.metadata["tool_calls"]`
as a list of `{"name": str, "args": dict}`.
"""
from __future__ import annotations

from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
    scorer,
)
from inspect_ai.solver import TaskState


@scorer(metrics=[accuracy(), mean()])
def tool_call_match() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        expected = state.metadata.get("expected_tools") or []
        forbidden = set(state.metadata.get("must_NOT_call") or [])
        observed = state.metadata.get("tool_calls") or []

        observed_by_name: dict[str, dict] = {c["name"]: c.get("args") or {} for c in observed}

        misses: list[str] = []
        for exp in expected:
            name = exp["name"]
            if name not in observed_by_name:
                misses.append(f"missing-tool:{name}")
                continue
            args = observed_by_name[name]
            for required in exp.get("must_have", []):
                if required not in args:
                    misses.append(f"missing-arg:{name}.{required}")

        wrongly_called = [c["name"] for c in observed if c["name"] in forbidden]
        if wrongly_called:
            misses.append(f"forbidden:{','.join(wrongly_called)}")

        if misses:
            return Score(value=INCORRECT, explanation="; ".join(misses))
        return Score(value=CORRECT, explanation="all expected tools called, no forbidden tools")

    return score
