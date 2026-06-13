"""Layer 3 — Tool call correctness.

Each case is a multi-turn volunteer conversation; expected output is a
tool trace (which tools, with which args, in which order — with a set
of forbidden tools).

Phase 1 stub: imports + loads the dataset; solver is a placeholder that
sets an empty tool trace. Real solver lands in Week 2 once the seeded
demo tenant fixture is wired up.
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.solver import Generate, TaskState, solver

from evals.scorers.tool_call_match import tool_call_match


@solver
def conversation_replay_solver():
    """Stub. Phase 2 will:
    - Spin up the seeded tenant from metadata.tenant_seed
    - Iterate each user message through the engagement agent
    - Collect tool calls into state.metadata["tool_calls"]
    - Stuff the final agent message into state.output.completion
    """
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.metadata.setdefault("tool_calls", [])
        state.output.completion = "[stub] phase 2 will replay this conversation"
        return state

    return solve


@task
def tool_call_correctness() -> Task:
    return Task(
        dataset=json_dataset(
            str(Path(__file__).parent.parent / "datasets" / "volunteer_signup.jsonl")
        ),
        solver=conversation_replay_solver(),
        scorer=tool_call_match(),
    )
