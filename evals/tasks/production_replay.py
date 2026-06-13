"""Layer 6 — Production replay.

Weekly cron: pulls a stratified sample from agent_call_log + conversation,
redacts PII, drops the result under datasets/production_replay/YYYY-WW.jsonl.

Eval re-runs each conversation through the current prompts and asks an
LLM judge whether the new reply is "at least as good as" the historical
one. Drift detector, not a PR blocker.
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
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


def _latest_replay_sample() -> Path | None:
    base = Path(__file__).parent.parent / "datasets" / "production_replay"
    if not base.exists():
        return None
    samples = sorted(base.glob("*.jsonl"))
    return samples[-1] if samples else None


@solver
def replay_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Phase 2: call the same agent that originally handled the
        # message and capture its new reply for diff scoring.
        state.output.completion = "[stub] phase 2 will replay through the current agent"
        return state

    return solve


@scorer(metrics=[accuracy()])
def at_least_as_good():
    async def score(state: TaskState, target: Target) -> Score:
        # Phase 2: LLM judge compares state.output.completion vs.
        # state.metadata["historical_reply"]. For now, mark PARTIAL so
        # the report is visibly "needs implementation".
        return Score(value=PARTIAL, explanation="stub — phase 2 will diff against historical")

    return score


@task
def production_replay() -> Task:
    latest = _latest_replay_sample()
    if latest is None:
        # First run before the harvester has dropped anything — emit a
        # synthetic empty dataset so `inspect eval` doesn't blow up.
        return Task(
            dataset=[Sample(input="[no replay samples yet]", target="ok")],
            solver=replay_solver(),
            scorer=at_least_as_good(),
        )
    return Task(
        dataset=json_dataset(str(latest)),
        solver=replay_solver(),
        scorer=at_least_as_good(),
    )
