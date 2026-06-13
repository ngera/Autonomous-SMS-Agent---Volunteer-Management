"""Eval-case management API.

SUPER_ADMIN-only surface. Lets the founder (or whoever maintains the
eval suite) browse the JSONL datasets, author new cases from natural
language via Claude, review/edit drafts, and approve them into the
on-disk dataset files.

The JSONL files under ``evals/datasets/`` are the source of truth. No
DB table — datasets are git-tracked. Drafts are kept ephemerally in
the response payload until the caller hits POST/PUT to persist.

Layer → file mapping is defined by ``_LAYER_FILES``. Each layer also
ships a JSON-schema-ish hint that the NL→draft endpoint uses to keep
Claude's output well-shaped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.dependencies import SuperAdminUser
from app.core.logging import get_logger

logger = get_logger("api.eval_cases")

router = APIRouter(prefix="/api/v1/eval-cases", tags=["eval-cases"])

# Repo root resolves relative to this file: backend/app/api/eval_cases.py -> ../../../
_REPO_ROOT = Path(__file__).resolve().parents[3]
_EVALS_DIR = _REPO_ROOT / "evals"
_DATASETS_DIR = _EVALS_DIR / "datasets"
_LOGS_DIR = _REPO_ROOT / "logs"
_UI_LOGS_DIR = _LOGS_DIR / "ui"

# Default model for ad-hoc runs from the UI. Layer 1 + 5 don't use it
# (deterministic), but Inspect AI requires a model arg.
_DEFAULT_MODEL = "anthropic/claude-haiku-4-5"

# In-process registry of in-flight runs triggered from the UI. Lost on
# process restart — acceptable since the resulting .eval file (once the
# subprocess finishes) is the source of truth and gets surfaced by the
# history endpoint.
_ACTIVE_RUNS: dict[str, dict[str, Any]] = {}


# ── Layer registry ──

class LayerSpec(BaseModel):
    key: str
    label: str
    dataset_file: str
    task_name: str  # matches the @task function name in evals/tasks/*.py
    target_examples: list[str]
    description: str
    schema_hint: dict[str, Any]


_LAYER_SPECS: dict[str, LayerSpec] = {
    "regex_router": LayerSpec(
        key="regex_router",
        label="Layer 1 — Regex router",
        dataset_file="regex_router.jsonl",
        task_name="regex_routing",
        target_examples=[
            "start_campaign",
            "start_campaign_bare",
            "delete_campaign",
            "delete_campaign_pronoun",
            "list_events",
            "no_match",
        ],
        description=(
            "Deterministic checks on the Tier 1 regex router. Each case "
            "asserts that a given admin message matches the right pattern "
            "bucket (or no_match for negatives)."
        ),
        schema_hint={
            "id": "kebab-case slug, e.g. muster-start-explicit-001",
            "input": "the admin SMS message exactly as typed",
            "target": "one of: start_campaign | start_campaign_bare | delete_campaign | delete_campaign_pronoun | list_events | no_match",
            "metadata": {
                "expected_extract": "optional: {label?, date?, subject?} the regex should capture",
                "note": "optional: one short sentence explaining the case",
            },
        },
    ),
    "intent_classifier": LayerSpec(
        key="intent_classifier",
        label="Layer 2 — Intent classifier",
        dataset_file="intent_classifier.jsonl",
        task_name="intent_classification",
        target_examples=[
            "start_planning",
            "approve",
            "delete_muster",
            "cancel_muster",
            "restart_muster",
            "list_events",
            "status",
            "other",
        ],
        description=(
            "Classifier-level checks. Each case asserts the LLM router "
            "returns the right intent + an event_reference substring + "
            "passes a confidence floor."
        ),
        schema_hint={
            "id": "kebab-case slug",
            "input": "the admin SMS message",
            "target": "one of: start_planning | approve | delete_muster | cancel_muster | restart_muster | list_events | status | other",
            "metadata": {
                "expected_event_reference": "optional: substring expected in classifier's event_reference output",
                "confidence_floor": "optional float 0..1 (default 0.7)",
                "destructive": "optional bool: true for delete-muster cases that should require confirmation",
                "note": "optional",
            },
        },
    ),
    "volunteer_signup": LayerSpec(
        key="volunteer_signup",
        label="Layer 3 — Tool call correctness",
        dataset_file="volunteer_signup.jsonl",
        task_name="tool_call_correctness",
        target_examples=["book_appointment", "switch_service", "cancel_appointment"],
        description=(
            "Multi-turn volunteer conversation. Asserts the engagement "
            "agent fires the right tools in any order with the right args, "
            "and does not call forbidden tools."
        ),
        schema_hint={
            "id": "kebab-case slug",
            "input": "newline-separated user messages (one per turn)",
            "target": "final tool name the test treats as the 'success' anchor",
            "metadata": {
                "tenant_seed": "demo-org-fresh | two-tenants-with-overlap",
                "expected_tools": "list of {name, must_have:[arg_name,...]}",
                "must_NOT_call": "list of tool names",
                "final_reply_rubric": "one sentence rubric for the final agent reply",
            },
        },
    ),
    "recruiter_planner": LayerSpec(
        key="recruiter_planner",
        label="Layer 4 — Recruiter plan quality",
        dataset_file="recruiter_planner.jsonl",
        task_name="recruiter_plan_quality",
        target_examples=["valid_plan", "needs_clarification"],
        description=(
            "Recruiter wave plan quality. Scored against a 4-axis "
            "LLM-judge rubric (right_sized_first_wave, service_volunteer_fit, "
            "honors_privacy, message_voice)."
        ),
        schema_hint={
            "id": "kebab-case slug",
            "input": "one-line description: event + services (min/max) + available pool",
            "target": "valid_plan",
            "metadata": {
                "available_volunteers": "int",
                "expected_plan_constraints": {
                    "wave_count": "[lo, hi]",
                    "first_wave_size": "[lo, hi]",
                    "no_volunteer_in_two_services": "bool",
                },
                "rubric": "recruiter_plan",
            },
        },
    ),
    "privacy_visibility": LayerSpec(
        key="privacy_visibility",
        label="Layer 5 — Privacy + multi-tenancy",
        dataset_file="privacy_visibility.jsonl",
        task_name="privacy_visibility",
        target_examples=["no_pii_leak", "share_on_roster=hidden"],
        description=(
            "Security boundary. Asserts the agent's reply does NOT "
            "include forbidden PII strings (cross-tenant data, hidden "
            "volunteers). Pure substring assertions — no LLM judge."
        ),
        schema_hint={
            "id": "kebab-case slug",
            "input": "the query string",
            "target": "no_pii_leak",
            "metadata": {
                "tenant_seed": "demo-org-fresh | two-tenants-with-overlap",
                "asking_tenant": "tenant-a | tenant-b",
                "must_NOT_appear_in_reply": "list of forbidden substrings",
                "note": "what each forbidden string represents",
            },
        },
    ),
}


# ── Models ──

class EvalCase(BaseModel):
    id: str
    input: str
    target: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalCaseList(BaseModel):
    layer: str
    count: int
    cases: list[EvalCase]


class LayerListResponse(BaseModel):
    layers: list[LayerSpec]


class DraftRequest(BaseModel):
    layer: str
    description: str = Field(..., min_length=4, max_length=2000)


class DraftResponse(BaseModel):
    layer: str
    draft: EvalCase
    reasoning: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ── Helpers ──

def _layer_or_404(layer: str) -> LayerSpec:
    spec = _LAYER_SPECS.get(layer)
    if not spec:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown layer '{layer}'. Valid: {sorted(_LAYER_SPECS)}",
        )
    return spec


def _read_jsonl(path: Path) -> list[EvalCase]:
    if not path.exists():
        return []
    out: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            out.append(EvalCase(**row))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Skipping malformed line in %s: %s", path.name, e)
    return out


def _write_jsonl(path: Path, cases: list[EvalCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")


def _dataset_path(spec: LayerSpec) -> Path:
    return _DATASETS_DIR / spec.dataset_file


# ── Routes ──

@router.get("/layers", response_model=LayerListResponse)
async def list_layers(current_user: SuperAdminUser) -> LayerListResponse:
    return LayerListResponse(layers=list(_LAYER_SPECS.values()))


@router.get("", response_model=EvalCaseList)
async def list_cases(
    current_user: SuperAdminUser,
    layer: str = Query(..., description="Layer key, e.g. 'regex_router'"),
) -> EvalCaseList:
    spec = _layer_or_404(layer)
    cases = _read_jsonl(_dataset_path(spec))
    return EvalCaseList(layer=layer, count=len(cases), cases=cases)


@router.get("/{layer}/{case_id}", response_model=EvalCase)
async def get_case(
    layer: str,
    case_id: str,
    current_user: SuperAdminUser,
) -> EvalCase:
    spec = _layer_or_404(layer)
    cases = _read_jsonl(_dataset_path(spec))
    for c in cases:
        if c.id == case_id:
            return c
    raise HTTPException(404, f"Case '{case_id}' not found in {layer}")


@router.post("/{layer}", response_model=EvalCase, status_code=201)
async def create_case(
    layer: str,
    case: EvalCase,
    current_user: SuperAdminUser,
) -> EvalCase:
    spec = _layer_or_404(layer)
    cases = _read_jsonl(_dataset_path(spec))
    if any(c.id == case.id for c in cases):
        raise HTTPException(
            409,
            f"Case id '{case.id}' already exists in {layer}. PUT to update.",
        )
    cases.append(case)
    _write_jsonl(_dataset_path(spec), cases)
    logger.info("Eval case appended: layer=%s id=%s", layer, case.id)
    return case


@router.put("/{layer}/{case_id}", response_model=EvalCase)
async def update_case(
    layer: str,
    case_id: str,
    case: EvalCase,
    current_user: SuperAdminUser,
) -> EvalCase:
    spec = _layer_or_404(layer)
    cases = _read_jsonl(_dataset_path(spec))
    for i, c in enumerate(cases):
        if c.id == case_id:
            # If the caller renamed the id, allow it as long as the new
            # id isn't taken.
            if case.id != case_id and any(
                other.id == case.id for j, other in enumerate(cases) if j != i
            ):
                raise HTTPException(
                    409, f"Cannot rename to '{case.id}' — id already used."
                )
            cases[i] = case
            _write_jsonl(_dataset_path(spec), cases)
            logger.info(
                "Eval case updated: layer=%s id=%s -> %s",
                layer, case_id, case.id,
            )
            return case
    raise HTTPException(404, f"Case '{case_id}' not found in {layer}")


@router.delete("/{layer}/{case_id}", status_code=204)
async def delete_case(
    layer: str,
    case_id: str,
    current_user: SuperAdminUser,
) -> None:
    spec = _layer_or_404(layer)
    cases = _read_jsonl(_dataset_path(spec))
    kept = [c for c in cases if c.id != case_id]
    if len(kept) == len(cases):
        raise HTTPException(404, f"Case '{case_id}' not found in {layer}")
    _write_jsonl(_dataset_path(spec), kept)
    logger.info("Eval case deleted: layer=%s id=%s", layer, case_id)


# ── NL → Draft ──

_DRAFT_SYSTEM_PROMPT = """You convert plain-English test descriptions \
from a developer into structured AI eval cases for a volunteer-booking \
SaaS called mustr.

You will be given:
  1. A LAYER specification (the kind of eval test).
  2. A SCHEMA HINT (what fields the JSON output must include).
  3. EXAMPLES of existing cases in this layer.
  4. The developer's PROSE description of the case they want.

Your job: produce ONE JSON object that fits the schema and exercises the \
behavior described. Keep the case minimal, deterministic, and \
self-explanatory.

OUTPUT FORMAT — strict JSON, no markdown fence, no prose:

{
  "case": {
    "id": "<kebab-case slug>",
    "input": "<the input as the schema describes>",
    "target": "<one of the allowed targets>",
    "metadata": { ... }
  },
  "reasoning": "<one short sentence explaining why this case exercises the behavior the developer described>",
  "warnings": ["<short string>", ...]
}

Rules:
- Generate a stable, descriptive id. Suffix with -001 (Phase 1 — caller \
  will bump if dup).
- If the developer's description is ambiguous, pick the most useful \
  interpretation AND add a warning explaining the assumption.
- Never invent a target that isn't in the layer's allowed-target list.
- Stay grounded in the EXAMPLES — don't introduce new metadata fields \
  that the schema hint doesn't mention.
- Keep input short and quoted exactly as a real user would type it."""


def _build_draft_user_prompt(spec: LayerSpec, examples: list[EvalCase], description: str) -> str:
    sample_block = "\n".join(
        json.dumps(c.model_dump(), ensure_ascii=False) for c in examples[:4]
    )
    return (
        f"LAYER: {spec.label}\n"
        f"DESCRIPTION: {spec.description}\n\n"
        f"ALLOWED TARGETS: {spec.target_examples}\n\n"
        f"SCHEMA HINT:\n{json.dumps(spec.schema_hint, indent=2)}\n\n"
        f"EXAMPLES (existing cases in this layer):\n{sample_block or '<none yet>'}\n\n"
        f"DEVELOPER'S DESCRIPTION:\n{description}\n\n"
        "Produce the JSON now."
    )


def _parse_draft_response(raw: str) -> tuple[EvalCase, str | None, list[str]] | None:
    raw = raw.strip()
    # Strip optional markdown fence.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    case_data = data.get("case")
    if not isinstance(case_data, dict):
        return None
    try:
        case = EvalCase(**case_data)
    except (ValueError, TypeError):
        return None
    return case, data.get("reasoning"), list(data.get("warnings") or [])


@router.post("/draft", response_model=DraftResponse)
async def draft_case_from_prose(
    payload: DraftRequest,
    current_user: SuperAdminUser,
) -> DraftResponse:
    """Convert a developer's prose description into a draft eval case
    via Claude. Caller reviews + edits + POSTs the case to persist."""
    spec = _layer_or_404(payload.layer)
    examples = _read_jsonl(_dataset_path(spec))

    api_key = settings.anthropic_api_key
    if not api_key:
        raise HTTPException(503, "Eval drafting unavailable: no Anthropic key configured.")

    user_prompt = _build_draft_user_prompt(spec, examples, payload.description)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": "claude-haiku-4-5",
                    "max_tokens": 600,
                    "system": _DRAFT_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Eval drafting HTTP error: %s", exc)
        raise HTTPException(502, f"Drafting API call failed: {exc}")

    if response.status_code != 200:
        logger.warning("Eval drafting non-200: %d %s", response.status_code, response.text[:200])
        raise HTTPException(502, f"Drafting API returned {response.status_code}")

    try:
        raw = response.json()["content"][0]["text"]
    except (KeyError, IndexError, ValueError) as exc:
        raise HTTPException(502, f"Drafting API malformed: {exc}")

    parsed = _parse_draft_response(raw)
    if parsed is None:
        logger.warning("Drafting model returned unparseable JSON: %r", raw[:200])
        # Return a stub draft so the UI can show the raw output and let
        # the admin hand-fix it instead of dead-ending.
        stub = EvalCase(
            id=f"draft-{uuid.uuid4().hex[:8]}",
            input=payload.description[:200],
            target=spec.target_examples[0] if spec.target_examples else "",
            metadata={"_raw_model_output": raw[:500]},
        )
        return DraftResponse(
            layer=payload.layer,
            draft=stub,
            reasoning=None,
            warnings=["Model output was not valid JSON — raw text stored in metadata for hand-fix."],
        )

    case, reasoning, warnings = parsed

    # Ensure id is unique within this dataset; suffix if not.
    existing_ids = {c.id for c in examples}
    if case.id in existing_ids:
        base = case.id.rsplit("-", 1)[0] if "-" in case.id else case.id
        for n in range(2, 100):
            candidate = f"{base}-{n:03d}"
            if candidate not in existing_ids:
                warnings.append(f"id '{case.id}' already used — bumped to '{candidate}'")
                case = case.model_copy(update={"id": candidate})
                break

    return DraftResponse(
        layer=payload.layer,
        draft=case,
        reasoning=reasoning,
        warnings=warnings,
    )


# ──────────────────────────────────────────────────────────────────────
# Run history + triggering
#
# .eval files (the source of truth) live in `logs/`. Inspect AI organizes
# them into subdirs by run context — we use:
#   logs/pr/           CI pull-request runs
#   logs/nightly/      CI nightly runs
#   logs/weekly/       CI weekly production-replay
#   logs/smoke/        manual CLI smoke tests
#   logs/ui/{run_id}/  runs triggered from the admin UI
#
# History endpoints read .eval files via inspect_ai.log. Trigger endpoint
# spawns `python -m inspect_ai eval ...` in a subprocess (no in-process
# coupling to Inspect's own asyncio loop) and tracks PID + log_dir in
# ``_ACTIVE_RUNS`` until completion.


class RunSummary(BaseModel):
    """Lightweight per-run row for the history table."""
    run_id: str
    task: str
    layer_key: str | None  # mapped from task name; None if task unknown
    model: str
    created_at: str
    status: str  # 'success' | 'error' | 'cancelled' | 'started'
    log_path: str
    bucket: str  # subdir under logs/ (pr | nightly | weekly | smoke | ui | other)
    total_samples: int
    scores: dict[str, dict[str, float]]


class RunSample(BaseModel):
    id: str
    input: str
    target: str
    output: str | None
    scores: dict[str, dict[str, Any]]


class RunDetail(RunSummary):
    samples: list[RunSample]
    error: str | None = None


class ActiveRun(BaseModel):
    run_id: str
    layer: str
    status: str  # 'queued' | 'running' | 'done' | 'error'
    started_at: str
    finished_at: str | None = None
    log_path: str | None = None
    error: str | None = None


class StartRunRequest(BaseModel):
    layer: str
    model: str | None = None


_TASK_TO_LAYER_KEY = {spec.task_name: spec.key for spec in _LAYER_SPECS.values()}


def _bucket_from_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(_LOGS_DIR.resolve())
    except (ValueError, OSError):
        return "other"
    parts = rel.parts
    if not parts:
        return "other"
    return parts[0]


def _log_path_from_info(info: Any) -> str:
    """Inspect AI returns paths like 'file://...' — normalize to a local
    filesystem path string for everything downstream."""
    name = getattr(info, "name", None) or str(info)
    if name.startswith("file://"):
        name = name[len("file://") :]
    return name


def _summary_from_log(info: Any, log: Any) -> RunSummary:
    log_path = _log_path_from_info(info)
    task_name = log.eval.task
    layer_key = _TASK_TO_LAYER_KEY.get(task_name)
    scores: dict[str, dict[str, float]] = {}
    if log.results:
        for s in log.results.scores or []:
            scores[s.name] = {
                metric: float(s.metrics[metric].value)
                for metric in s.metrics
            }
    p = Path(log_path)
    run_id = p.stem
    return RunSummary(
        run_id=run_id,
        task=task_name,
        layer_key=layer_key,
        model=log.eval.model,
        created_at=str(log.eval.created),
        status=log.status,
        log_path=str(p),
        bucket=_bucket_from_path(p),
        total_samples=(log.results.total_samples if log.results else 0),
        scores=scores,
    )


def _find_log_by_run_id(run_id: str) -> Any | None:
    from inspect_ai.log import list_eval_logs

    if not _LOGS_DIR.exists():
        return None
    infos = list_eval_logs(str(_LOGS_DIR), recursive=True)
    for info in infos:
        p = Path(_log_path_from_info(info))
        if p.stem == run_id:
            return info
    return None


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    current_user: SuperAdminUser,
    layer: str | None = Query(default=None),
    bucket: str | None = Query(default=None, description="Filter by subdir under logs/"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[RunSummary]:
    from inspect_ai.log import list_eval_logs, read_eval_log

    if not _LOGS_DIR.exists():
        return []

    infos = list_eval_logs(str(_LOGS_DIR), recursive=True, descending=True)

    out: list[RunSummary] = []
    for info in infos[: limit * 2]:
        try:
            log = read_eval_log(info.name, header_only=True)
        except Exception as e:  # noqa: BLE001 - keep history robust
            logger.warning("Skipping unreadable log %s: %s", info.name, e)
            continue
        summary = _summary_from_log(info, log)
        if layer and summary.layer_key != layer:
            continue
        if bucket and summary.bucket != bucket:
            continue
        out.append(summary)
        if len(out) >= limit:
            break
    return out


@router.get("/runs/active", response_model=list[ActiveRun])
async def list_active_runs(current_user: SuperAdminUser) -> list[ActiveRun]:
    """In-flight UI-triggered runs. Finished records hang around for 5
    minutes so the UI can show the done/error transition."""
    now = datetime.now(timezone.utc)
    out: list[ActiveRun] = []
    expired: list[str] = []
    for run_id, rec in _ACTIVE_RUNS.items():
        finished_at = rec.get("finished_at")
        if finished_at:
            try:
                fin = datetime.fromisoformat(finished_at)
                if (now - fin).total_seconds() > 300:
                    expired.append(run_id)
                    continue
            except ValueError:
                pass
        out.append(ActiveRun(**{k: v for k, v in rec.items() if k != "_task_ref"}))
    for k in expired:
        _ACTIVE_RUNS.pop(k, None)
    return sorted(out, key=lambda r: r.started_at, reverse=True)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    current_user: SuperAdminUser,
) -> RunDetail:
    from inspect_ai.log import read_eval_log

    info = _find_log_by_run_id(run_id)
    if info is None:
        raise HTTPException(404, f"Run '{run_id}' not found in logs/")

    try:
        log = read_eval_log(info.name, header_only=False)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Could not read log: {e}")

    summary = _summary_from_log(info, log)

    samples: list[RunSample] = []
    for s in log.samples or []:
        s_scores: dict[str, dict[str, Any]] = {}
        for name, sc in (s.scores or {}).items():
            s_scores[name] = {
                "value": sc.value,
                "explanation": sc.explanation,
                "answer": getattr(sc, "answer", None),
            }
        target_val = s.target
        if isinstance(target_val, list):
            target_str = ", ".join(str(t) for t in target_val)
        else:
            target_str = str(target_val) if target_val is not None else ""
        samples.append(
            RunSample(
                id=str(s.id),
                input=str(s.input)[:2000],
                target=target_str,
                output=(s.output.completion if s.output else None),
                scores=s_scores,
            )
        )

    return RunDetail(
        **summary.model_dump(),
        samples=samples,
        error=(log.error.message if log.error else None),
    )


# ── Trigger ─────────────────────────────────────────────────────────


async def _run_subprocess(run_id: str, layer: str, model: str) -> None:
    """Background task: spawn `python -m inspect_ai eval <task_file>`
    and update the active-run record when it finishes."""
    spec = _LAYER_SPECS.get(layer)
    if not spec:
        _ACTIVE_RUNS[run_id].update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": f"Unknown layer '{layer}'",
        })
        return

    task_file_abs = _EVALS_DIR / "tasks" / f"{spec.task_name}.py"
    if not task_file_abs.exists():
        _ACTIVE_RUNS[run_id].update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": f"Task file missing: {task_file_abs}",
        })
        return

    log_dir_abs = _UI_LOGS_DIR / run_id
    log_dir_abs.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    backend_path = str(_REPO_ROOT / "backend")
    env["PYTHONPATH"] = backend_path + os.pathsep + env.get("PYTHONPATH", "")

    # Inspect AI's CLI uses pathlib.Path.glob() which rejects absolute
    # paths on Windows ("Non-relative patterns are unsupported"). Pass
    # paths relative to the repo root (cwd) so the same command works on
    # Windows + Linux CI.
    task_file_rel = task_file_abs.relative_to(_REPO_ROOT).as_posix()
    log_dir_rel = log_dir_abs.relative_to(_REPO_ROOT).as_posix()

    cmd = [
        sys.executable,
        "-m",
        "inspect_ai",
        "eval",
        task_file_rel,
        "--model",
        model,
        "--log-dir",
        log_dir_rel,
    ]
    logger.info(
        "Starting eval subprocess: run_id=%s layer=%s",
        run_id, layer,
    )

    _ACTIVE_RUNS[run_id]["status"] = "running"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(_REPO_ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        rc = proc.returncode or 0
    except Exception as e:  # noqa: BLE001
        _ACTIVE_RUNS[run_id].update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": f"subprocess spawn failed: {e}",
        })
        return

    produced = sorted(log_dir_abs.glob("*.eval"))
    log_path = str(produced[-1]) if produced else None

    if rc != 0:
        err_tail = (stderr or b"").decode("utf-8", "replace")[-1500:]
        logger.warning("Eval subprocess failed (rc=%d): %s", rc, err_tail)
        _ACTIVE_RUNS[run_id].update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "log_path": log_path,
            "error": f"rc={rc}; stderr tail: {err_tail[-500:]}",
        })
        return

    _ACTIVE_RUNS[run_id].update({
        "status": "done",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "log_path": log_path,
        "error": None,
    })
    logger.info(
        "Eval subprocess done: run_id=%s layer=%s log=%s",
        run_id, layer, log_path,
    )


@router.post("/runs", response_model=ActiveRun, status_code=202)
async def start_run(
    payload: StartRunRequest,
    current_user: SuperAdminUser,
) -> ActiveRun:
    """Trigger an eval run in the background. Returns immediately with a
    run_id; poll /runs/active to track status."""
    spec = _layer_or_404(payload.layer)
    # One in-flight run per layer at a time. Cheap guardrail against
    # accidental click-storms.
    for rec in _ACTIVE_RUNS.values():
        if rec["layer"] == spec.key and rec["status"] in {"queued", "running"}:
            raise HTTPException(
                409,
                f"A run for layer '{spec.key}' is already in flight "
                f"(run_id={rec['run_id']}, status={rec['status']}).",
            )

    run_id = uuid.uuid4().hex[:12]
    rec = {
        "run_id": run_id,
        "layer": spec.key,
        "status": "queued",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "log_path": None,
        "error": None,
    }
    _ACTIVE_RUNS[run_id] = rec

    model = payload.model or _DEFAULT_MODEL
    # Hold a strong ref so the GC doesn't collect mid-run (same pattern
    # used in chat_tools._BACKGROUND_TASKS).
    task = asyncio.create_task(_run_subprocess(run_id, spec.key, model))
    _ACTIVE_RUNS[run_id]["_task_ref"] = task

    return ActiveRun(**{k: v for k, v in rec.items() if k != "_task_ref"})
