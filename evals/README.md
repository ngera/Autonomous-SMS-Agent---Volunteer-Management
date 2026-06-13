# mustr — Evals

AI eval framework. Plan: [docs/eval_framework_plan.md](../docs/eval_framework_plan.md).

Six layers, cheapest first. Layers 1, 2, 5 gate every PR; 3 and 4 run nightly;
6 runs weekly.

| # | Layer | Task module | Dataset |
|---|---|---|---|
| 1 | Regex router | [tasks/regex_routing.py](tasks/regex_routing.py) | [datasets/regex_router.jsonl](datasets/regex_router.jsonl) |
| 2 | Intent classifier | [tasks/intent_classification.py](tasks/intent_classification.py) | [datasets/intent_classifier.jsonl](datasets/intent_classifier.jsonl) |
| 3 | Tool call correctness | [tasks/tool_call_correctness.py](tasks/tool_call_correctness.py) | [datasets/volunteer_signup.jsonl](datasets/volunteer_signup.jsonl) |
| 4 | Agent message quality | [tasks/recruiter_plan_quality.py](tasks/recruiter_plan_quality.py) | [datasets/recruiter_planner.jsonl](datasets/recruiter_planner.jsonl) |
| 5 | Privacy + multi-tenancy | [tasks/privacy_visibility.py](tasks/privacy_visibility.py) | [datasets/privacy_visibility.jsonl](datasets/privacy_visibility.jsonl) |
| 6 | Production replay | [tasks/production_replay.py](tasks/production_replay.py) | [datasets/production_replay/](datasets/production_replay/) |

## Setup

```bash
# Install eval deps. Reuses Python 3.12 from the backend venv.
pip install -r evals/requirements.txt

# Backend imports rely on the package layout — set PYTHONPATH.
export PYTHONPATH=backend
export ANTHROPIC_API_KEY=...   # for Layers 2, 3, 4, 6
```

## Run

```bash
# Fast PR set (Layers 1, 2, 5) — ~60s wall time.
./evals/runners/run_pr_evals.sh

# Full nightly set (Layers 1-5).
./evals/runners/run_nightly.sh

# Production replay (Layer 6, weekly).
inspect eval evals/tasks/production_replay.py
```

Individual layer:

```bash
inspect eval evals/tasks/regex_routing.py
inspect eval evals/tasks/intent_classification.py --model anthropic/claude-haiku-4-5
```

Reports land under `logs/` (HTML + JSON). Open with `inspect view`.

## Adding a test case

1. Append a JSON line to the relevant `datasets/*.jsonl`.
2. Field schema follows Inspect AI: `input` (the message / scenario), `target`
   (expected output), optional `metadata` (anything the scorer needs).
3. Run the single layer locally before pushing — `inspect eval evals/tasks/<layer>.py`.

## Gating thresholds

Defined in each task file (`epochs`, `scorer` reductions). Mirrors the plan:

- Layer 1: positive accuracy >=0.95, false positive <=0.02 (PR blocker)
- Layer 2: overall accuracy not down >2pp vs. baseline (PR blocker)
- Layer 5: zero misses (PR blocker)
- Layer 3: correctness >=0.90 (nightly alert)
- Layer 4: each axis >=3.5 average (nightly alert)
- Layer 6: "no worse" rate >=0.92 (weekly drift signal)
