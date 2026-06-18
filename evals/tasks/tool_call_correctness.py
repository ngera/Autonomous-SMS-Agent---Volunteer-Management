"""Layer 3 — Tool call correctness.

Each case is a multi-turn volunteer conversation; the target asserts
which tools the engagement agent calls and what args it passes.

The solver replays the conversation through the *production*
`run_tool_conversation` loop from `app.modules.tool_executor`, with a
per-case ``handlers`` override that returns canned responses from
`metadata.tool_responses`. That keeps the eval hermetic — no DB, no
real tenant — while exercising the real LLM tool-selection behavior
through the real tool-use protocol.

Case schema additions vs. the v1 stub:
- ``metadata.preamble``       — tenant context the model needs (services,
                                upcoming events, existing bookings, today's
                                date). Replaces the per-tenant context block
                                that production builds from DB.
- ``metadata.tool_responses`` — dict of {tool_name: canned JSON string}. The
                                solver wires each entry into a fake handler.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.solver import Generate, TaskState, solver

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.scorers.tool_call_match import tool_call_match


_BASE_SYSTEM = """You are mustr, a friendly SMS assistant for a nonprofit \
that helps volunteers sign up, switch, or cancel commitments. Keep replies \
warm, brief, and fit one SMS segment when possible. Use the available \
tools to look up availability and book appointments rather than answering \
from memory.

ROSTER VISIBILITY: book_appointment accepts an optional `share_on_roster` \
arg (hidden | first_name | full_name). If the volunteer mentions a \
preference (e.g. "show my first name", "keep my name hidden"), pass it \
through. If the preamble below shows a saved default, use that and don't \
re-ask. Otherwise ask once.

Don't call `list_services` if the preamble already enumerates the \
available services."""


def _build_handlers(tool_responses: dict) -> dict:
    """Return an async-handler dict that returns each tool's canned
    response verbatim. The closure trick (default arg) freezes each
    response so all handlers don't end up sharing the last loop value."""
    handlers: dict = {}
    for tool_name, response in tool_responses.items():
        if isinstance(response, (dict, list)):
            payload = json.dumps(response)
        else:
            payload = str(response)

        async def _handler(_ctx, _tool_input, _payload=payload):
            return _payload

        handlers[tool_name] = _handler
    return handlers


def _make_stub_ctx():
    """A ToolContext-shaped object that never touches the DB. We use a
    plain dataclass instance rather than SimpleNamespace because
    handlers downstream may access `ctx.tool_calls.append(...)` etc."""
    from app.modules.tool_handlers import ToolContext  # type: ignore

    # Construct via __new__ + manual field set to avoid the typed
    # constraint on `db` / `tenant` (we pass None, which is fine because
    # no handler we register will dereference them).
    ctx = ToolContext.__new__(ToolContext)
    ctx.db = None  # type: ignore[assignment]
    ctx.tenant = None  # type: ignore[assignment]
    ctx.contact_phone = "+15555550100"
    ctx.contact_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ctx.is_admin = False
    ctx.test_mode = True
    ctx.booking_created = False
    ctx.booking_cancelled = False
    ctx.booking_rescheduled = False
    ctx.tool_calls = []
    return ctx


@solver
def conversation_replay_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Lazy imports — these chain through chat_tools, which we
        # decycled earlier. Importing inside the solver also keeps the
        # task file importable when the backend env isn't fully set up
        # (Inspect AI discovers tasks before evaluating).
        from app.modules.tool_definitions import CUSTOMER_TOOLS  # type: ignore
        from app.modules.tool_executor import run_tool_conversation  # type: ignore

        meta = state.metadata or {}
        preamble = str(meta.get("preamble") or "")
        tool_responses = meta.get("tool_responses") or {}

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            state.output.completion = "[error] no ANTHROPIC_API_KEY in env"
            state.metadata["tool_calls"] = []
            return state

        ctx = _make_stub_ctx()
        handlers = _build_handlers(tool_responses)

        system_prompt = (
            _BASE_SYSTEM + "\n\nVOLUNTEER STATE / TENANT CONTEXT\n" + preamble
        )

        # Split the conversation. Cases author one user message per line.
        user_messages = [
            line.strip()
            for line in str(state.input_text).splitlines()
            if line.strip()
        ]

        messages: list[dict] = []
        last_text = ""
        for user_msg in user_messages:
            messages.append({"role": "user", "content": user_msg})
            try:
                result = await run_tool_conversation(
                    system_prompt=system_prompt,
                    tools=CUSTOMER_TOOLS,
                    messages=messages,
                    ctx=ctx,
                    api_key=api_key,
                    model="claude-haiku-4-5",
                    handlers=handlers,
                    max_rounds=5,
                )
            except Exception as e:  # noqa: BLE001
                state.output.completion = f"[error] turn failed: {type(e).__name__}: {e}"
                state.metadata["tool_calls"] = _translate(ctx.tool_calls)
                return state
            last_text = result.text or ""
            # Append the final assistant text so the next user turn has
            # correct user/assistant alternation. run_tool_conversation
            # only mutates `messages` with intermediate tool_use/result
            # pairs — never with the final end_turn text.
            messages.append({"role": "assistant", "content": last_text})

        state.metadata["tool_calls"] = _translate(ctx.tool_calls)
        state.output.completion = last_text
        return state

    return solve


def _translate(tool_calls: list[dict]) -> list[dict]:
    """Production records tool_calls as {tool, input, output}; the
    scorer wants {name, args}. Translate at the boundary."""
    return [
        {"name": tc.get("tool", ""), "args": tc.get("input") or {}}
        for tc in tool_calls
    ]


@task
def tool_call_correctness() -> Task:
    return Task(
        dataset=json_dataset(
            str(Path(__file__).parent.parent / "datasets" / "volunteer_signup.jsonl")
        ),
        solver=conversation_replay_solver(),
        scorer=tool_call_match(),
    )
