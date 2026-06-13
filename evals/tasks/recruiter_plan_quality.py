"""Layer 4 — Recruiter wave plan message quality.

Each case describes an event + service shape + available pool; the
target is "valid_plan". We score the recruiter planner's output across
the 4-axis recruiter_plan rubric via LLM-as-judge.

Phase 1 stub: loads dataset, runs the LLM judge with a placeholder
agent output. Real solver lands in Week 2 — calls
`app.agents.recruiter.planner.run_planner` and stuffs the wave plan
into state.output.completion.
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.solver import Generate, TaskState, solver

from evals.scorers.llm_as_judge_sms import llm_as_judge_sms


@solver
def planner_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Phase 2: call run_planner against a seeded tenant + stuff the
        # wave plan + draft SMS into state.output.completion.
        state.output.completion = "[stub] phase 2 will run the real planner"
        return state

    return solve


@task
def recruiter_plan_quality() -> Task:
    return Task(
        dataset=json_dataset(
            str(Path(__file__).parent.parent / "datasets" / "recruiter_planner.jsonl")
        ),
        solver=planner_solver(),
        scorer=llm_as_judge_sms(rubric_name="recruiter_plan"),
    )
