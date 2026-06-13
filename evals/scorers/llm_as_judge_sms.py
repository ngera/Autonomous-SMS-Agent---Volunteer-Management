"""Rubric-based SMS quality scorer using Claude Haiku as the judge.

Loads a rubric from `evals/rubrics/<name>.md`, presents the agent's
output + the case context to the judge model, and parses a 1-5 score
per axis. Average across axes is the headline score; per-axis scores
land in the explanation for drill-down.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, get_model
from inspect_ai.scorer import (
    Score,
    Scorer,
    Target,
    mean,
    scorer,
)
from inspect_ai.solver import TaskState

RUBRICS_DIR = Path(__file__).resolve().parent.parent / "rubrics"

_JUDGE_MODEL = "anthropic/claude-haiku-4-5"

_INSTRUCTION = """You are scoring an AI agent's output against a rubric.

For each axis in the rubric, output a JSON object:
  {"axis": "<name>", "score": <int 1-5>, "reason": "<one short sentence>"}

Output a SINGLE JSON array of these objects. No prose, no markdown fence."""


def _load_rubric(name: str) -> str:
    path = RUBRICS_DIR / f"{name}.md"
    if not path.exists():
        return f"[Rubric {name} not yet authored — use generic helpfulness scoring]"
    return path.read_text(encoding="utf-8")


def _parse_scores(raw: str) -> list[dict]:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


@scorer(metrics=[mean()])
def llm_as_judge_sms(rubric_name: str = "sms_quality") -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        rubric = _load_rubric(rubric_name)
        output = state.output.completion or ""
        context = state.metadata.get("context") or state.input_text

        judge = get_model(_JUDGE_MODEL)
        msg = await judge.generate(
            input=[
                ChatMessageSystem(content=_INSTRUCTION),
                ChatMessageUser(
                    content=(
                        f"RUBRIC\n------\n{rubric}\n\n"
                        f"AGENT INPUT / CONTEXT\n---------------------\n{context}\n\n"
                        f"AGENT OUTPUT\n------------\n{output}"
                    )
                ),
            ]
        )

        parsed = _parse_scores(msg.completion)
        if not parsed:
            return Score(value=0, explanation=f"judge returned unparseable: {msg.completion[:200]}")

        per_axis = {item.get("axis", f"axis_{i}"): item.get("score", 0) for i, item in enumerate(parsed)}
        avg = sum(per_axis.values()) / max(len(per_axis), 1)
        return Score(value=avg, answer=msg.completion, explanation=json.dumps(per_axis))

    return score
